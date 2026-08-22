from __future__ import annotations

import base64
import binascii
import ctypes
import errno
import json
import os
import re
import secrets
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
from .trust import load_control_plane_json, trusted_approvers_path


BROKER_STATE_FILE = (
    Path("/private/var/db/sddgov/consumed-nonces.jsonl")
    if sys.platform == "darwin"
    else Path("/var/lib/sddgov/consumed-nonces.jsonl")
)
BROKER_SOCKET_GROUP = "_sddgov" if sys.platform == "darwin" else "sddgov"
MAX_REQUEST_BYTES = 2048
MAX_LEDGER_RECORD_BYTES = 2048
MAX_LEDGER_BYTES = 64 * 1024 * 1024
LEDGER_CAPACITY_WARNING_PERCENT = 80
MAX_CONSECUTIVE_ACCEPT_FAILURES = 5
INITIAL_ACCEPT_BACKOFF_SECONDS = 0.1
MAX_ACCEPT_BACKOFF_SECONDS = 2.0
REQUEST_READ_DEADLINE_SECONDS = 2.0
RESPONSE_SEND_DEADLINE_SECONDS = 2.0
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
BROKER_STAGING_DIRECTORY = ".broker-staging"
LINUX_RENAME_NOREPLACE = 1
DARWIN_RENAME_EXCL = 0x00000004


def _stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _broker_log(message: str) -> None:
    """Emit operational metadata without logging request or receipt contents."""
    if sys.platform == "darwin":
        import syslog as system_log

        system_log.openlog(
            "sddgov-broker", system_log.LOG_PID, system_log.LOG_DAEMON
        )
        system_log.syslog(system_log.LOG_WARNING, message)
        return
    print(message, file=sys.stderr, flush=True)


def _write_all(descriptor: int, value: bytes) -> None:
    offset = 0
    while offset < len(value):
        written = os.write(descriptor, value[offset:])
        if written <= 0:
            raise OSError("broker ledger write made no progress")
        offset += written


def _warn_ledger_capacity(size: int) -> None:
    if size * 100 >= MAX_LEDGER_BYTES * LEDGER_CAPACITY_WARNING_PERCENT:
        _broker_log(
            "L3 Broker ledger capacity warning: "
            f"{size}/{MAX_LEDGER_BYTES} bytes used; schedule controlled epoch rollover"
        )


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
        if os.fstat(descriptor).st_size >= MAX_LEDGER_BYTES:
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
            _warn_ledger_capacity(os.fstat(descriptor).st_size)
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
            current_size = os.fstat(descriptor).st_size
            if current_size + len(record) >= MAX_LEDGER_BYTES:
                raise ValueError(
                    "broker ledger would exceed the active-epoch capacity limit; "
                    "complete the controlled epoch rollover runbook"
                )
            seen_nonces = self._scan_locked(descriptor)
            if nonce in seen_nonces:
                return False
            os.lseek(descriptor, 0, os.SEEK_END)
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
    """Read one bounded record until the client half-closes its write side.

    After sending the newline-terminated record, clients must call
    ``shutdown(SHUT_WR)`` so the Broker observes EOF before the read deadline.
    """
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
    if len(value) > MAX_REQUEST_BYTES:
        raise ValueError("broker request exceeds the size limit")
    if bytes(value).count(b"\n") != 1 or not value.endswith(b"\n"):
        raise ValueError("broker request must be exactly one newline-terminated record")
    return bytes(value)


def _handle_connection(connection: socket.socket, ledger: NonceLedger) -> None:
    try:
        response = handle_request(_receive_request(connection), ledger)
    except (OSError, ValueError) as exc:
        _broker_log(f"L3 Broker rejected request: {exc}")
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


def receive_broker_health_response(
    client: socket.socket,
    *,
    timeout_seconds: float,
) -> bytes:
    """Read a bounded Broker health response through one monotonic deadline."""
    expected = b"READY\n"
    response = bytearray()
    deadline = time.monotonic() + timeout_seconds
    while len(response) <= len(expected):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise socket.timeout("Broker health response deadline exceeded")
        client.settimeout(remaining)
        chunk = client.recv(len(expected) + 1 - len(response))
        if not chunk:
            break
        response.extend(chunk)
    return bytes(response)


def _broker_health() -> None:
    request = b'{"action":"health"}\n'
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(str(L3_NONCE_BROKER))
        client.sendall(request)
        client.shutdown(socket.SHUT_WR)
        response = receive_broker_health_response(client, timeout_seconds=5)
    if response != b"READY\n":
        raise ValueError("L3 Broker did not return the exact health response")


def _approver_store(root: Path) -> dict[str, Any]:
    source = trusted_approvers_path(root)
    value = load_control_plane_json(source, "fixed trusted approver store")
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


def _exclusive_rename_at(
    source_directory: int,
    source_name: str,
    destination_directory: int,
    destination_name: str,
) -> None:
    """Publish a pathname atomically without replacing an existing entry."""
    if (
        "/" in source_name
        or "/" in destination_name
        or not source_name
        or not destination_name
    ):
        raise ValueError("exclusive rename requires single path components")
    if sys.platform == "linux":
        symbol = "renameat2"
        flag = LINUX_RENAME_NOREPLACE
    elif sys.platform == "darwin":
        symbol = "renameatx_np"
        flag = DARWIN_RENAME_EXCL
    else:
        raise ValueError("exclusive Broker socket publication requires Linux or macOS")
    library = ctypes.CDLL(None, use_errno=True)
    operation = getattr(library, symbol, None)
    if operation is None:
        raise ValueError(f"platform libc does not expose required {symbol}")
    operation.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    operation.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = operation(
        source_directory,
        os.fsencode(source_name),
        destination_directory,
        os.fsencode(destination_name),
        flag,
    )
    if result != 0:
        error = ctypes.get_errno() or errno.EIO
        raise OSError(error, os.strerror(error), destination_name)


def _stat_at(directory: int, name: str) -> os.stat_result:
    return os.stat(name, dir_fd=directory, follow_symlinks=False)


def _socket_path_identity(metadata: os.stat_result) -> tuple[int, int]:
    if not stat.S_ISSOCK(metadata.st_mode):
        raise ValueError("L3 Broker bind did not create a Unix socket pathname")
    return metadata.st_dev, metadata.st_ino


def _open_broker_directories(
    socket_path: Path, *, owner_uid: int
) -> tuple[int, int]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    parent_descriptor = os.open(socket_path.parent, flags)
    try:
        parent_metadata = os.fstat(parent_descriptor)
        path_metadata = socket_path.parent.lstat()
        if (
            not stat.S_ISDIR(parent_metadata.st_mode)
            or (parent_metadata.st_dev, parent_metadata.st_ino)
            != (path_metadata.st_dev, path_metadata.st_ino)
            or parent_metadata.st_uid != owner_uid
            or parent_metadata.st_mode & 0o022
        ):
            raise ValueError("L3 Broker socket parent changed or is writable")
        try:
            os.mkdir(BROKER_STAGING_DIRECTORY, 0o700, dir_fd=parent_descriptor)
        except FileExistsError:
            pass
        staging_descriptor = os.open(
            BROKER_STAGING_DIRECTORY,
            flags,
            dir_fd=parent_descriptor,
        )
        try:
            staging_metadata = os.fstat(staging_descriptor)
            named_metadata = _stat_at(
                parent_descriptor, BROKER_STAGING_DIRECTORY
            )
            if (
                not stat.S_ISDIR(staging_metadata.st_mode)
                or (staging_metadata.st_dev, staging_metadata.st_ino)
                != (named_metadata.st_dev, named_metadata.st_ino)
                or staging_metadata.st_uid != owner_uid
                or stat.S_IMODE(staging_metadata.st_mode) != 0o700
            ):
                raise ValueError(
                    "L3 Broker staging directory must be owner-only and stable"
                )
        except Exception:
            os.close(staging_descriptor)
            raise
    except Exception:
        os.close(parent_descriptor)
        raise
    return parent_descriptor, staging_descriptor


def _unlink_socket_if_identity(
    directory: int,
    name: str,
    expected_identity: tuple[int, int],
    *,
    stat_at=_stat_at,
) -> None:
    pending = ""
    for _ in range(4):
        candidate = f".broker-cleanup-{secrets.token_hex(16)}.sock"
        try:
            _exclusive_rename_at(directory, name, directory, candidate)
        except FileNotFoundError:
            return
        except FileExistsError:
            continue
        pending = candidate
        break
    if not pending:
        raise ValueError("L3 Broker socket cleanup could not reserve a private name")

    def restore_claim(primary: BaseException | None = None) -> None:
        try:
            _exclusive_rename_at(directory, pending, directory, name)
        except FileNotFoundError:
            return
        except FileExistsError as exc:
            error = ValueError(
                "L3 Broker socket changed during cleanup; "
                f"preserved pending generation {pending}"
            )
            if primary is not None:
                raise primary from error
            raise error from exc
        except BaseException as exc:
            error = ValueError(
                "L3 Broker socket cleanup could not restore the original name; "
                f"preserved pending generation {pending}"
            )
            if primary is not None:
                raise primary from error
            raise error from exc

    try:
        metadata = stat_at(directory, pending)
    except BaseException as primary:
        restore_claim(primary)
        raise
    if (
        stat.S_ISSOCK(metadata.st_mode)
        and (metadata.st_dev, metadata.st_ino) == expected_identity
    ):
        try:
            os.unlink(pending, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.fsync(directory)
        return
    restore_claim()
    os.fsync(directory)


def _publish_broker_socket(
    server: socket.socket,
    socket_path: Path,
    group_id: int,
    *,
    owner_uid: int,
    parent_descriptor: int,
    staging_descriptor: int,
    stat_at=_stat_at,
) -> tuple[int, int]:
    final_name = socket_path.name
    try:
        stat_at(parent_descriptor, final_name)
    except FileNotFoundError:
        pass
    else:
        raise ValueError("L3 Broker socket path already exists; inspect it before restart")

    staging_name = f"broker-{secrets.token_hex(16)}.sock"
    staging_path = socket_path.parent / BROKER_STAGING_DIRECTORY / staging_name
    staging_identity: tuple[int, int] | None = None
    published = False
    publication_verified = False
    server.bind(str(staging_path))
    try:
        try:
            staging_metadata = stat_at(staging_descriptor, staging_name)
        except Exception:
            # The staging directory is owner-only and descriptor-anchored. Before
            # the first pathname identity can be captured, only this exclusive,
            # unpredictable staging entry is safe to remove. The final pathname
            # has not been published and is never touched on this path.
            try:
                os.unlink(staging_name, dir_fd=staging_descriptor)
            except FileNotFoundError:
                pass
            raise
        staging_identity = _socket_path_identity(staging_metadata)
        _configure_socket_access(
            staging_path,
            group_id,
            staging_identity,
            owner_uid=owner_uid,
        )
        _exclusive_rename_at(
            staging_descriptor,
            staging_name,
            parent_descriptor,
            final_name,
        )
        published = True
        final_metadata = stat_at(parent_descriptor, final_name)
        if (
            not stat.S_ISSOCK(final_metadata.st_mode)
            or (final_metadata.st_dev, final_metadata.st_ino) != staging_identity
        ):
            raise ValueError("L3 Broker socket identity changed during publication")
        publication_verified = True
        return staging_identity
    finally:
        if not published and staging_identity is not None:
            _unlink_socket_if_identity(
                staging_descriptor,
                staging_name,
                staging_identity,
                stat_at=stat_at,
            )
        elif published and not publication_verified and staging_identity is not None:
            _unlink_socket_if_identity(
                parent_descriptor,
                final_name,
                staging_identity,
                stat_at=stat_at,
            )


def _serve_requests(server: socket.socket, ledger: NonceLedger, should_stop) -> None:
    server.listen(32)
    server.settimeout(1.0)
    consecutive_accept_failures = 0
    accept_backoff = INITIAL_ACCEPT_BACKOFF_SECONDS
    while not should_stop():
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
            _broker_log(
                "L3 Broker accept failure "
                f"{consecutive_accept_failures}/{MAX_CONSECUTIVE_ACCEPT_FAILURES}: {exc}"
            )
            if consecutive_accept_failures >= MAX_CONSECUTIVE_ACCEPT_FAILURES:
                raise OSError(
                    "L3 Broker stopped after repeated accept failures"
                ) from exc
            time.sleep(accept_backoff)
            accept_backoff = min(MAX_ACCEPT_BACKOFF_SECONDS, accept_backoff * 2)
            continue
        consecutive_accept_failures = 0
        accept_backoff = INITIAL_ACCEPT_BACKOFF_SECONDS
        with connection:
            _handle_connection(connection, ledger)


def _serve_broker_at(
    socket_path: Path,
    ledger: NonceLedger,
    group_id: int,
    *,
    owner_uid: int,
) -> None:
    ledger.initialize()
    shutdown_requested = False
    previous_handlers: dict[int, Any] = {}
    published_identity: tuple[int, int] | None = None
    parent_descriptor: int | None = None
    staging_descriptor: int | None = None

    def request_shutdown(_signum: int, _frame: Any) -> None:
        nonlocal shutdown_requested
        shutdown_requested = True

    for signum in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signum] = signal.signal(signum, request_shutdown)
    try:
        parent_descriptor, staging_descriptor = _open_broker_directories(
            socket_path, owner_uid=owner_uid
        )
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            published_identity = _publish_broker_socket(
                server,
                socket_path,
                group_id,
                owner_uid=owner_uid,
                parent_descriptor=parent_descriptor,
                staging_descriptor=staging_descriptor,
            )
            _serve_requests(server, ledger, lambda: shutdown_requested)
    finally:
        if published_identity is not None and parent_descriptor is not None:
            _unlink_socket_if_identity(
                parent_descriptor,
                socket_path.name,
                published_identity,
            )
        if staging_descriptor is not None:
            os.close(staging_descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)


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
    _serve_broker_at(
        L3_NONCE_BROKER,
        NonceLedger(),
        group_id,
        owner_uid=0,
    )
