from __future__ import annotations

import base64
import binascii
import json
import os
import re
import signal
import socket
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
    import grp
except ImportError:  # pragma: no cover - exercised by native non-POSIX hosts
    fcntl = None  # type: ignore[assignment]
    grp = None  # type: ignore[assignment]

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .autonomy import L3_NONCE_BROKER, L3_RUNTIME_CONTEXT_FILE, _runtime_context
from .trust import load_control_plane_json


BROKER_STATE_FILE = (
    Path("/private/var/db/sddgov/consumed-nonces.jsonl")
    if sys.platform == "darwin"
    else Path("/var/lib/sddgov/consumed-nonces.jsonl")
)
BROKER_SOCKET_GROUP = "_sddgov" if sys.platform == "darwin" else "sddgov"
MAX_REQUEST_BYTES = 2048
MAX_LEDGER_RECORD_BYTES = 2048
MAX_LEDGER_BYTES = 64 * 1024 * 1024
MAX_CONSECUTIVE_ACCEPT_FAILURES = 5
INITIAL_ACCEPT_BACKOFF_SECONDS = 0.1
MAX_ACCEPT_BACKOFF_SECONDS = 2.0
REQUEST_READ_DEADLINE_SECONDS = 2.0
RESPONSE_SEND_DEADLINE_SECONDS = 2.0
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _write_all(descriptor: int, value: bytes) -> None:
    offset = 0
    while offset < len(value):
        written = os.write(descriptor, value[offset:])
        if written <= 0:
            raise OSError("broker ledger write made no progress")
        offset += written


class NonceLedger:
    """Append-only single-use nonce ledger protected by a process lock."""

    def __init__(
        self,
        path: Path = BROKER_STATE_FILE,
        *,
        expected_uid: int = 0,
        validate_parent_chain: bool = True,
    ) -> None:
        self.path = path
        self.expected_uid = expected_uid
        self.validate_parent_chain = validate_parent_chain

    def _open(self, *, create: bool) -> int:
        if fcntl is None:
            raise ValueError("L3 Broker nonce ledger requires Linux or macOS")
        if self.validate_parent_chain:
            errors = _root_owned_directory_errors(self.path.parent)
            if errors:
                raise ValueError("; ".join(errors))
        flags = (
            os.O_RDWR
            | os.O_APPEND
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        if create:
            try:
                descriptor = os.open(
                    self.path,
                    flags | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError:
                descriptor = os.open(self.path, flags)
                created = False
            else:
                created = True
        else:
            descriptor = os.open(self.path, flags)
            created = False
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != self.expected_uid
            or metadata.st_mode & 0o077
        ):
            os.close(descriptor)
            raise ValueError(
                "broker ledger must be a single-linked, owner-only regular file"
            )
        if created:
            try:
                parent_descriptor = os.open(
                    self.path.parent,
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                )
                try:
                    os.fsync(parent_descriptor)
                finally:
                    os.close(parent_descriptor)
            except OSError:
                os.close(descriptor)
                raise
        return descriptor

    @staticmethod
    def _scan_locked(descriptor: int) -> set[str]:
        if os.fstat(descriptor).st_size > MAX_LEDGER_BYTES:
            raise ValueError(
                "broker ledger exceeds the active-epoch capacity limit; "
                "complete the controlled epoch rollover runbook"
            )
        os.lseek(descriptor, 0, os.SEEK_SET)
        seen_nonces: set[str] = set()
        with os.fdopen(os.dup(descriptor), "rb") as handle:
            while True:
                line = handle.readline(MAX_LEDGER_RECORD_BYTES + 1)
                if not line:
                    break
                if len(line) > MAX_LEDGER_RECORD_BYTES or not line.endswith(b"\n"):
                    raise ValueError("broker ledger contains an invalid record")
                try:
                    row = json.loads(line[:-1].decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("broker ledger contains an invalid record") from exc
                if not _valid_ledger_record(row) or row["nonce"] in seen_nonces:
                    raise ValueError("broker ledger contains an invalid record")
                seen_nonces.add(row["nonce"])
        return seen_nonces

    def initialize(self) -> None:
        descriptor = self._open(create=True)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            self._scan_locked(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def validate(self) -> None:
        descriptor = self._open(create=False)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            self._scan_locked(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def consume(
        self, nonce: str, receipt_sha256: str, operation_payload_sha256: str
    ) -> bool:
        descriptor = self._open(create=False)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            seen_nonces = self._scan_locked(descriptor)
            if nonce in seen_nonces:
                return False
            record = json.dumps(
                {
                    "nonce": nonce,
                    "receipt_sha256": receipt_sha256,
                    "operation_payload_sha256": operation_payload_sha256,
                    "consumed_at": _stamp(),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8") + b"\n"
            if os.lseek(descriptor, 0, os.SEEK_END) + len(record) > MAX_LEDGER_BYTES:
                raise ValueError(
                    "broker ledger would exceed the active-epoch capacity limit; "
                    "complete the controlled epoch rollover runbook"
                )
            _write_all(descriptor, record)
            os.fsync(descriptor)
            return True
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _valid_ledger_record(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "nonce",
        "receipt_sha256",
        "operation_payload_sha256",
        "consumed_at",
    }:
        return False
    consumed_at = value.get("consumed_at")
    if (
        not _valid_nonce_fields(value)
        or not isinstance(consumed_at, str)
        or not consumed_at.endswith("Z")
    ):
        return False
    try:
        parsed = datetime.fromisoformat(consumed_at.removesuffix("Z") + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _valid_nonce_fields(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    nonce = value.get("nonce")
    return (
        isinstance(nonce, str)
        and 12 <= len(nonce) <= 256
        and all(0x21 <= ord(character) <= 0x7E for character in nonce)
        and isinstance(value.get("receipt_sha256"), str)
        and SHA256_PATTERN.fullmatch(value["receipt_sha256"]) is not None
        and isinstance(value.get("operation_payload_sha256"), str)
        and SHA256_PATTERN.fullmatch(value["operation_payload_sha256"]) is not None
    )


def _parse_request(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise ValueError("broker request must be exactly one newline-terminated record")
    try:
        request = json.loads(raw[:-1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("broker request must be valid UTF-8 JSON") from exc
    if not isinstance(request, dict):
        raise ValueError("broker request must be a JSON object")
    return request


def handle_request(raw: bytes, ledger: NonceLedger) -> bytes:
    request = _parse_request(raw)
    if request == {"action": "health"}:
        ledger.validate()
        return b"READY\n"
    if set(request) != {
        "action",
        "nonce",
        "receipt_sha256",
        "operation_payload_sha256",
    } or request.get("action") != "consume":
        return b"REJECTED\n"
    if not _valid_nonce_fields(request):
        return b"REJECTED\n"
    consumed = ledger.consume(
        request["nonce"],
        request["receipt_sha256"],
        request["operation_payload_sha256"],
    )
    return b"CONSUMED\n" if consumed else b"ALREADY_CONSUMED\n"


def _receive_request(connection: socket.socket) -> bytes:
    deadline = time.monotonic() + REQUEST_READ_DEADLINE_SECONDS
    value = bytearray()
    while len(value) <= MAX_REQUEST_BYTES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("broker request exceeded the read deadline")
        connection.settimeout(remaining)
        chunk = connection.recv(min(512, MAX_REQUEST_BYTES + 1 - len(value)))
        if not chunk:
            break
        value.extend(chunk)
        if b"\n" in value:
            break
    if len(value) > MAX_REQUEST_BYTES:
        raise ValueError("broker request exceeds the size limit")
    return bytes(value)


def _handle_connection(connection: socket.socket, ledger: NonceLedger) -> None:
    try:
        response = handle_request(_receive_request(connection), ledger)
    except (OSError, ValueError) as exc:
        print(f"L3 Broker rejected request: {exc}", file=sys.stderr, flush=True)
        response = b"REJECTED\n"
    try:
        connection.settimeout(RESPONSE_SEND_DEADLINE_SECONDS)
        connection.sendall(response)
    except OSError:
        # A client may disconnect after sending a request. Its timeout or broken
        # pipe must not terminate the root-owned broker daemon.
        pass


def _root_owned_directory_errors(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_absolute():
        return [f"control-plane path must be absolute: {path}"]
    for directory in reversed((path, *path.parents)):
        try:
            metadata = directory.lstat()
        except OSError as exc:
            errors.append(f"control-plane directory is unavailable: {directory}: {exc}")
            break
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != 0
            or metadata.st_mode & 0o022
        ):
            errors.append(
                f"control-plane directory must be root-owned and not writable by group/other: {directory}"
            )
            break
    return errors


def _socket_errors() -> list[str]:
    errors = _root_owned_directory_errors(L3_NONCE_BROKER.parent)
    try:
        metadata = L3_NONCE_BROKER.lstat()
    except OSError as exc:
        return errors + [f"L3 Broker socket is unavailable: {exc}"]
    if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != 0:
        errors.append("L3 Broker socket must be a root-owned Unix socket")
    if stat.S_IMODE(metadata.st_mode) != 0o660:
        errors.append("L3 Broker socket mode must be exactly 0660")
    if grp is None:
        errors.append("L3 Broker socket group lookup requires Linux or macOS")
    else:
        try:
            expected_group_id = grp.getgrnam(BROKER_SOCKET_GROUP).gr_gid
        except KeyError:
            errors.append(
                f"L3 Broker dedicated group does not exist: {BROKER_SOCKET_GROUP}"
            )
        else:
            if metadata.st_gid != expected_group_id:
                errors.append(
                    "L3 Broker socket must use the dedicated group "
                    f"{BROKER_SOCKET_GROUP}"
                )
    return errors


def _broker_health() -> None:
    request = b'{"action":"health"}\n'
    response = bytearray()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(str(L3_NONCE_BROKER))
        client.sendall(request)
        client.shutdown(socket.SHUT_WR)
        while len(response) <= len(b"READY\n"):
            chunk = client.recv(len(b"READY\n") + 1 - len(response))
            if not chunk:
                break
            response.extend(chunk)
    if bytes(response) != b"READY\n":
        raise ValueError("L3 Broker did not return the exact health response")


def _approver_store(root: Path) -> dict[str, Any]:
    source_value = os.environ.get("SDDGOV_TRUSTED_APPROVERS_FILE")
    if not source_value:
        raise ValueError("SDDGOV_TRUSTED_APPROVERS_FILE is not configured")
    source = Path(source_value).expanduser().absolute()
    try:
        source.resolve().relative_to(root.resolve())
    except ValueError:
        value = load_control_plane_json(source, "out-of-band trusted approver store")
    else:
        raise ValueError("trusted approver store must be outside the repository")
    if (
        set(value) != {"schema_version", "approvers"}
        or value.get("schema_version") != "1.0"
        or not isinstance(value.get("approvers"), list)
        or not value["approvers"]
    ):
        raise ValueError("trusted approver store has an invalid contract")
    seen: set[str] = set()
    active = 0
    for row in value["approvers"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"approver_id", "algorithm", "public_key", "status"}
            or not isinstance(row.get("approver_id"), str)
            or not row["approver_id"].strip()
            or row.get("algorithm") != "ed25519"
            or row.get("status") not in {"active", "revoked"}
            or not isinstance(row.get("public_key"), str)
            or row["approver_id"] in seen
        ):
            raise ValueError("trusted approver store has an invalid record")
        seen.add(row["approver_id"])
        try:
            public_key = base64.b64decode(row["public_key"], validate=True)
            Ed25519PublicKey.from_public_bytes(public_key)
        except (ValueError, binascii.Error, UnsupportedAlgorithm) as exc:
            raise ValueError("trusted approver store has an invalid Ed25519 key") from exc
        active += row["status"] == "active"
    if active == 0:
        raise ValueError("trusted approver store has no active key")
    return {"path": str(source), "approvers": len(seen), "active": active}


def broker_readiness(root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, operation) -> None:
        try:
            detail = operation()
        except (OSError, ValueError) as exc:
            checks.append({"name": name, "ok": False, "detail": str(exc)})
        else:
            checks.append({"name": name, "ok": True, "detail": detail})

    def supported_platform() -> str:
        if os.name != "posix" or sys.platform not in {"linux", "darwin"}:
            raise ValueError("L3 Broker requires Linux or macOS")
        return sys.platform

    def agent_identity_separation() -> dict[str, int]:
        if not hasattr(os, "geteuid") or os.geteuid() == 0:
            raise ValueError("Agent process must not run as root")
        return {"euid": os.geteuid()}

    check("supported_platform", supported_platform)
    check("agent_identity_separation", agent_identity_separation)
    check("runtime_context", _runtime_context)
    check("trusted_approver_store", lambda: _approver_store(root))

    def socket_check() -> dict[str, str]:
        errors = _socket_errors()
        if errors:
            raise ValueError("; ".join(errors))
        _broker_health()
        return {"socket": str(L3_NONCE_BROKER), "health": "READY"}

    check("broker_socket", socket_check)
    errors = [row["detail"] for row in checks if not row["ok"]]
    return {
        "ok": not errors,
        "state": "READY" if not errors else "NOT_READY",
        "checks": checks,
        "errors": errors,
        "next_action": (
            "L3 receipts may be imported and consumed"
            if not errors
            else "complete docs/L3_BROKER_OPERATIONS.md before any real L3 operation"
        ),
    }


def _configure_socket_access(
    path: Path,
    group_id: int,
    expected_identity: tuple[int, int],
    *,
    owner_uid: int = 0,
) -> None:
    metadata = path.lstat()
    if (
        not stat.S_ISSOCK(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino) != expected_identity
    ):
        raise ValueError("L3 Broker socket identity changed during setup")
    # The entirely root-owned, non-writable parent chain prevents an untrusted
    # user from replacing this pathname. Plain path operations are required:
    # chmod(..., follow_symlinks=False) is unsupported for Unix sockets on Linux.
    if metadata.st_uid != owner_uid or metadata.st_gid != group_id:
        os.chown(path, owner_uid, group_id)
    if stat.S_IMODE(metadata.st_mode) != 0o660:
        os.chmod(path, 0o660)
    metadata = path.lstat()
    if (
        not stat.S_ISSOCK(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino) != expected_identity
        or metadata.st_uid != owner_uid
        or metadata.st_gid != group_id
        or stat.S_IMODE(metadata.st_mode) != 0o660
    ):
        raise ValueError("L3 Broker socket access changed during setup")


def serve_broker(socket_group: str) -> None:
    if os.name != "posix" or sys.platform not in {"linux", "darwin"} or grp is None:
        raise ValueError("L3 Broker service requires Linux or macOS")
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise ValueError("L3 Broker service must run as root")
    if socket_group != BROKER_SOCKET_GROUP:
        raise ValueError(
            f"L3 Broker socket group must be {BROKER_SOCKET_GROUP} on this platform"
        )
    parent_errors = _root_owned_directory_errors(L3_NONCE_BROKER.parent)
    parent_errors.extend(_root_owned_directory_errors(BROKER_STATE_FILE.parent))
    if parent_errors:
        raise ValueError("; ".join(parent_errors))
    try:
        group_id = grp.getgrnam(socket_group).gr_gid
    except KeyError as exc:
        raise ValueError(f"L3 Broker group does not exist: {socket_group}") from exc
    if L3_NONCE_BROKER.exists() or L3_NONCE_BROKER.is_symlink():
        raise ValueError("L3 Broker socket path already exists; inspect it before restart")
    ledger = NonceLedger()
    ledger.initialize()
    shutdown_requested = False
    previous_handlers: dict[int, Any] = {}
    bound_socket_identity: tuple[int, int] | None = None

    def request_shutdown(_signum: int, _frame: Any) -> None:
        nonlocal shutdown_requested
        shutdown_requested = True

    for signum in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signum] = signal.signal(signum, request_shutdown)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(L3_NONCE_BROKER))
            socket_metadata = L3_NONCE_BROKER.lstat()
            if not stat.S_ISSOCK(socket_metadata.st_mode):
                raise ValueError("L3 Broker bind did not create a Unix socket")
            bound_socket_identity = (socket_metadata.st_dev, socket_metadata.st_ino)
            _configure_socket_access(
                L3_NONCE_BROKER,
                group_id,
                bound_socket_identity,
            )
            server.listen(32)
            server.settimeout(1.0)
            consecutive_accept_failures = 0
            accept_backoff = INITIAL_ACCEPT_BACKOFF_SECONDS
            while not shutdown_requested:
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    consecutive_accept_failures = 0
                    accept_backoff = INITIAL_ACCEPT_BACKOFF_SECONDS
                    continue
                except InterruptedError:
                    continue
                except OSError as exc:
                    consecutive_accept_failures += 1
                    print(
                        "L3 Broker accept failure "
                        f"{consecutive_accept_failures}/{MAX_CONSECUTIVE_ACCEPT_FAILURES}: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                    if consecutive_accept_failures >= MAX_CONSECUTIVE_ACCEPT_FAILURES:
                        raise OSError(
                            "L3 Broker stopped after repeated accept failures"
                        ) from exc
                    time.sleep(accept_backoff)
                    accept_backoff = min(
                        MAX_ACCEPT_BACKOFF_SECONDS,
                        accept_backoff * 2,
                    )
                    continue
                consecutive_accept_failures = 0
                accept_backoff = INITIAL_ACCEPT_BACKOFF_SECONDS
                with connection:
                    _handle_connection(connection, ledger)
    finally:
        if bound_socket_identity is not None:
            try:
                metadata = L3_NONCE_BROKER.lstat()
            except FileNotFoundError:
                pass
            else:
                if (
                    stat.S_ISSOCK(metadata.st_mode)
                    and (metadata.st_dev, metadata.st_ino) == bound_socket_identity
                ):
                    L3_NONCE_BROKER.unlink()
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)
