"""Owner-facing product approval without exposing signing keys to the Agent."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import socket
import stat
import struct
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import __version__
from .autonomy import (
    OWNER_CLIENT_BINDING_PREFIX,
    _canonical_receipt,
    _load_unique_json_bytes,
    _read_repository_regular_file,
    _trusted_approver,
    _trusted_approver_domain,
    _verify_product_envelope,
    evaluate_escalation,
)
from .fs_security import (
    open_directory_path,
    require_directory_path_identity,
    write_new_regular_file,
)


MAX_APPROVAL_REQUEST_BYTES = 1024 * 1024
MAX_ASSUMPTION_ARTIFACT_BYTES = 256 * 1024
MAX_ASSUMPTION_TOTAL_BYTES = 1024 * 1024
MAX_ASSUMPTION_PATHS = 8
MAX_CARD_FIELD_BYTES = 8192
MAX_RENDERED_CARD_BYTES = 32768
MAX_AGENT_MESSAGE_BYTES = 1024 * 1024
SSH_AGENTC_REQUEST_IDENTITIES = 11
SSH_AGENT_IDENTITIES_ANSWER = 12
SSH2_AGENTC_SIGN_REQUEST = 13
SSH2_AGENT_SIGN_RESPONSE = 14
SSH_AGENT_FAILURE = 5


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _read_owner_client_source(package_fd: int, name: str) -> bytes:
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=package_fd,
        )
        before = os.fstat(descriptor)
        path_before = os.stat(name, dir_fd=package_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino)
            != (path_before.st_dev, path_before.st_ino)
            or before.st_size > MAX_APPROVAL_REQUEST_BYTES
        ):
            raise ValueError("Owner client source identity cannot be read safely")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, MAX_APPROVAL_REQUEST_BYTES + 1 - size),
            )
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_APPROVAL_REQUEST_BYTES:
                raise ValueError("Owner client source identity exceeds the bounded size")
        after = os.fstat(descriptor)
        path_after = os.stat(name, dir_fd=package_fd, follow_symlinks=False)

        def snapshot(value: os.stat_result) -> tuple[int, ...]:
            return (
                value.st_dev,
                value.st_ino,
                value.st_mode,
                value.st_nlink,
                value.st_size,
                value.st_mtime_ns,
                value.st_ctime_ns,
            )

        if snapshot(before) != snapshot(after) or snapshot(after) != snapshot(path_after):
            raise ValueError("Owner client source identity changed while being read")
        closing_descriptor = descriptor
        descriptor = -1
        os.close(closing_descriptor)
        return b"".join(chunks)
    except BaseException:
        if descriptor >= 0:
            closing_descriptor = descriptor
            descriptor = -1
            try:
                os.close(closing_descriptor)
            except OSError:
                pass
        raise


def _owner_client_identity() -> dict[str, Any]:
    package_root = Path(__file__).absolute().parent
    files = (
        "__init__.py",
        "autonomy.py",
        "fs_security.py",
        "governance.py",
        "owner_approval.py",
        "owner_cli.py",
        "owner_launcher.sh",
        "trust.py",
    )
    rows = []
    package_fd = open_directory_path(package_root, "Owner client package")
    try:
        for name in files:
            raw = _read_owner_client_source(package_fd, name)
            rows.append(
                {"path": f"sddgov/{name}", "sha256": hashlib.sha256(raw).hexdigest()}
            )
        require_directory_path_identity(
            package_root,
            package_fd,
            "Owner client package",
        )
    finally:
        closing_package_fd = package_fd
        package_fd = -1
        try:
            os.close(closing_package_fd)
        except OSError:
            pass
    return {
        "version": __version__,
        "source_files": rows,
        "source_sha256": hashlib.sha256(_canonical_json(rows)).hexdigest(),
    }


def _safe_relative_path(value: str, label: str) -> PurePosixPath:
    pure = PurePosixPath(value)
    if (
        not value
        or "\x00" in value
        or "\\" in value
        or any(
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
            for character in value
        )
        or pure.is_absolute()
        or str(pure) != value
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ValueError(f"{label} must be a canonical repository-relative path")
    return pure


def _read_repository_json(root: Path, relative: str, label: str) -> dict[str, Any]:
    raw = _read_repository_regular_file(
        root,
        _safe_relative_path(relative, label),
        max_bytes=MAX_APPROVAL_REQUEST_BYTES,
    )
    value = _load_unique_json_bytes(raw, label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain one JSON object")
    return value


def _assumption_rows(root: Path, values: list[str]) -> tuple[list[dict[str, str]], str]:
    if not values:
        raise ValueError("at least one decision assumption artifact is required")
    if len(values) > MAX_ASSUMPTION_PATHS:
        raise ValueError("too many decision assumption artifacts")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    total_bytes = 0
    for value in values:
        pure = _safe_relative_path(value, "decision assumption")
        if value in seen:
            raise ValueError("decision assumption paths must be unique")
        seen.add(value)
        raw = _read_repository_regular_file(
            root,
            pure,
            max_bytes=MAX_ASSUMPTION_ARTIFACT_BYTES,
        )
        total_bytes += len(raw)
        if total_bytes > MAX_ASSUMPTION_TOTAL_BYTES:
            raise ValueError("decision assumption artifacts exceed the aggregate limit")
        rows.append({"path": value, "sha256": hashlib.sha256(raw).hexdigest()})
    digest = hashlib.sha256(_canonical_json(rows)).hexdigest()
    return rows, digest


def _validated_assumption_paths(request: dict[str, Any]) -> list[str]:
    values = request.get("assumption_paths")
    if not isinstance(values, list) or not values:
        raise ValueError(
            "product approval request requires canonical assumption_paths"
        )
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("product approval assumption_paths must contain strings")
        normalized.append(
            str(_safe_relative_path(value, "product approval assumption"))
        )
    if normalized != sorted(set(normalized)):
        raise ValueError(
            "product approval assumption_paths must be unique and canonically sorted"
        )
    return normalized


def _require_terminal_safe_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be one non-empty string")
    if any(
        unicodedata.category(character).startswith("C")
        or unicodedata.category(character) in {"Zl", "Zp"}
        for character in value
    ):
        raise ValueError(f"{label} contains terminal control or invisible text")
    if len(value.encode("utf-8")) > MAX_CARD_FIELD_BYTES:
        raise ValueError(f"{label} exceeds the bounded display size")
    return value


def _validated_owner_card(card: dict[str, Any]) -> None:
    for field in (
        "heading",
        "decision_id",
        "risk_level",
        "why_human_input_is_required",
        "recommended",
        "why",
        "impact_if_no_decision",
        "scope_of_approval",
        "approver_id",
        "repository_id",
        "trust_domain",
    ):
        _require_terminal_safe_text(card.get(field), f"product approval {field}")
    verified = card.get("what_agent_already_verified")
    if not isinstance(verified, list) or not verified:
        raise ValueError("product approval verified facts must be a non-empty list")
    for index, value in enumerate(verified):
        _require_terminal_safe_text(value, f"product approval verified fact {index}")
    options = card.get("options")
    if not isinstance(options, list) or len(options) != 2:
        raise ValueError("product approval card requires exactly options A and B")
    labels: list[str] = []
    for index, option in enumerate(options):
        if not isinstance(option, dict) or set(option) != {"label", "description"}:
            raise ValueError("product approval options have an invalid contract")
        labels.append(
            _require_terminal_safe_text(
                option.get("label"),
                f"product approval option {index} label",
            )
        )
        _require_terminal_safe_text(
            option.get("description"),
            f"product approval option {index} description",
        )
    if labels != ["A", "B"] or card.get("recommended") not in {"A", "B"}:
        raise ValueError("product approval card requires unique ordered labels A and B")
    if card.get("recommended") != "A":
        raise ValueError("product approval card requires A as the only approvable option")
    assumption_paths = card.get("assumption_paths")
    if (
        not isinstance(assumption_paths, list)
        or not assumption_paths
        or len(assumption_paths) > MAX_ASSUMPTION_PATHS
    ):
        raise ValueError("product approval card requires bounded assumption paths")
    normalized_paths: list[str] = []
    for index, value in enumerate(assumption_paths):
        safe = _require_terminal_safe_text(
            value,
            f"product approval assumption path {index}",
        )
        normalized_paths.append(
            str(_safe_relative_path(safe, "product approval assumption path"))
        )
    if normalized_paths != sorted(set(normalized_paths)):
        raise ValueError("product approval card assumption paths must be unique and sorted")
    valid_days = card.get("valid_days")
    if not isinstance(valid_days, int) or isinstance(valid_days, bool) or not 1 <= valid_days <= 366:
        raise ValueError("product approval validity must be between 1 and 366 days")
    client = card.get("owner_client")
    if not isinstance(client, dict) or set(client) != {
        "version",
        "source_files",
        "source_sha256",
    }:
        raise ValueError("product approval Owner client identity is invalid")
    _require_terminal_safe_text(
        client.get("version"),
        "product approval Owner client version",
    )
    source_sha256 = client.get("source_sha256")
    source_files = client.get("source_files")
    if (
        not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_sha256)
        or not isinstance(source_files, list)
        or not source_files
        or len(source_files) > 32
    ):
        raise ValueError("product approval Owner client identity is invalid")
    source_paths: list[str] = []
    for row in source_files:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("product approval Owner client source row is invalid")
        path = row.get("path")
        digest = row.get("sha256")
        if not isinstance(path, str):
            raise ValueError("product approval Owner client source path is invalid")
        safe_path = str(_safe_relative_path(path, "Owner client source path"))
        if not safe_path.startswith("sddgov/"):
            raise ValueError("product approval Owner client source path is invalid")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("product approval Owner client source digest is invalid")
        source_paths.append(safe_path)
    if source_paths != sorted(set(source_paths)) or not secrets.compare_digest(
        source_sha256,
        hashlib.sha256(_canonical_json(source_files)).hexdigest(),
    ):
        raise ValueError("product approval Owner client identity is invalid")
    if (
        not isinstance(card.get("approver_key_sha256"), str)
        or len(card["approver_key_sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in card["approver_key_sha256"])
    ):
        raise ValueError("product approval trusted Owner key identity is invalid")


def _trusted_owner_public_key(root: Path, approver_id: str) -> bytes:
    approver = _trusted_approver(root, approver_id)
    try:
        public_key = base64.b64decode(approver["public_key"], validate=True)
        Ed25519PublicKey.from_public_bytes(public_key)
    except (TypeError, ValueError) as exc:
        raise ValueError("trusted Owner public key is invalid") from exc
    return public_key


def build_product_approval_card(
    root: Path,
    request_path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate one L2 escalation request and return its bounded Owner card."""
    request = _read_repository_json(root, request_path, "product approval request")
    result = evaluate_escalation(root, request)
    if result.get("state") != "ACTION_REQUIRED" or result.get("requires_response") is not True:
        raise ValueError("product approval request is not one validated ACTION REQUIRED")
    card = result.get("decision_package")
    if not isinstance(card, dict) or card.get("risk_level") != "L2":
        raise ValueError("product approval request does not contain one validated L2 card")
    card = dict(card)
    assumption_paths = _validated_assumption_paths(request)
    assumptions, assumptions_sha256 = _assumption_rows(root, assumption_paths)
    card["assumption_paths"] = assumption_paths
    card["assumptions"] = assumptions
    card["assumptions_sha256"] = assumptions_sha256
    card["approver_id"] = _require_terminal_safe_text(
        request.get("approver_id"),
        "product approval approver_id",
    )
    public_key = _trusted_owner_public_key(root, card["approver_id"])
    card["approver_key_sha256"] = hashlib.sha256(public_key).hexdigest()
    binding = _trusted_approver_domain(root, card["approver_id"])
    card["repository_id"] = binding["repository_id"]
    card["trust_domain"] = binding["trust_domain"]
    card["valid_days"] = request.get("valid_days")
    actual_client = _owner_client_identity()
    expected_client = request.get("owner_client")
    if (
        not isinstance(expected_client, dict)
        or set(expected_client) != {"version", "source_sha256"}
        or expected_client.get("version") != actual_client["version"]
        or not isinstance(expected_client.get("source_sha256"), str)
        or not secrets.compare_digest(
            expected_client["source_sha256"],
            actual_client["source_sha256"],
        )
    ):
        raise ValueError(
            "installed Owner client does not match the governed reviewed source identity"
        )
    marker = (
        OWNER_CLIENT_BINDING_PREFIX
        + json.dumps(
            expected_client,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    ).encode("utf-8")
    bound_artifacts = 0
    for path in assumption_paths:
        raw_assumption = _read_repository_regular_file(
            root,
            PurePosixPath(path),
            max_bytes=MAX_ASSUMPTION_ARTIFACT_BYTES,
        )
        if marker in raw_assumption.splitlines():
            bound_artifacts += 1
    if bound_artifacts != 1:
        raise ValueError(
            "decision assumptions must bind one exact reviewed Owner client identity"
        )
    card["owner_client"] = actual_client
    _validated_owner_card(card)
    return request, card


def render_product_approval_card(card: dict[str, Any]) -> str:
    """Render only the product meaning an Owner must decide, never machine digests."""
    _validated_owner_card(card)
    options = card.get("options")
    if not isinstance(options, list) or not options:
        raise ValueError("product approval card has no options")
    lines = [
        "SDG OWNER DECISION",
        f"Decision: {card['decision_id']}",
        f"Risk: {card['risk_level']}",
        "",
        "Why your decision is required:",
        card["why_human_input_is_required"],
        "",
        "Already verified by Agents and machines:",
        *[f"- {fact}" for fact in card["what_agent_already_verified"]],
        "",
        "Scope:",
        card["scope_of_approval"],
        "",
        "Contract artifacts:",
        *[f"- {path}" for path in card["assumption_paths"]],
        "",
        f"Approver identity: {card['approver_id']}",
        f"Repository: {card['repository_id']}",
        f"Trust domain: {card['trust_domain']}",
        f"Owner client: SDG {card['owner_client']['version']} (matches governed reviewed source identity)",
        f"Receipt validity: {card['valid_days']} days",
        "",
        "Options:",
    ]
    for option in options:
        lines.append(f"[{option['label']}] {option['description']}")
    lines.extend(
        [
            "",
            f"Recommended: {card['recommended']}",
            card["why"],
            "",
            f"If unanswered: {card['impact_if_no_decision']}",
            "",
            "SDG computes and verifies the receipt, assumptions, nonce, and signature.",
        ]
    )
    rendered = "\n".join(lines) + "\n"
    if len(rendered.encode("utf-8")) > MAX_RENDERED_CARD_BYTES:
        raise ValueError("product approval card exceeds the bounded terminal size")
    return rendered


def product_approval_card_sha256(card: dict[str, Any]) -> str:
    """Bind an Owner-visible card to the receipt construction call."""
    return hashlib.sha256(_canonical_json(card)).hexdigest()


def _ssh_string(value: bytes) -> bytes:
    if len(value) > MAX_AGENT_MESSAGE_BYTES:
        raise ValueError("SSH agent field exceeds the bounded protocol size")
    return struct.pack(">I", len(value)) + value


def _take_ssh_string(payload: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(payload):
        raise ValueError("SSH agent returned a truncated string length")
    length = struct.unpack(">I", payload[offset : offset + 4])[0]
    offset += 4
    if length > MAX_AGENT_MESSAGE_BYTES or offset + length > len(payload):
        raise ValueError("SSH agent returned an invalid string length")
    return payload[offset : offset + length], offset + length


def _recv_exact(connection: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ValueError("SSH agent closed before returning a complete response")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _ssh_agent_exchange(socket_path: str, payload: bytes, timeout: float) -> bytes:
    if not socket_path or "\x00" in socket_path:
        raise ValueError("SSH_AUTH_SOCK is unavailable or invalid")
    if len(payload) > MAX_AGENT_MESSAGE_BYTES:
        raise ValueError("SSH agent request exceeds the bounded protocol size")
    connection: socket.socket | None = None
    try:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(timeout)
        connection.connect(socket_path)
        connection.sendall(struct.pack(">I", len(payload)) + payload)
        response_length = struct.unpack(">I", _recv_exact(connection, 4))[0]
        if response_length < 1 or response_length > MAX_AGENT_MESSAGE_BYTES:
            raise ValueError("SSH agent response has an invalid bounded length")
        return _recv_exact(connection, response_length)
    except (OSError, TimeoutError) as exc:
        raise ValueError("confirmed SSH signer is unavailable") from exc
    finally:
        try:
            if connection is not None:
                connection.close()
        except OSError:
            # Socket close is resource cleanup after the complete response was
            # received. It must not replace a signer refusal/protocol error or
            # turn a verified response into an ambiguous second signing attempt.
            pass


def _ed25519_key_blob(public_key: bytes) -> bytes:
    if len(public_key) != 32:
        raise ValueError("trusted Owner Ed25519 public key must contain 32 raw bytes")
    return _ssh_string(b"ssh-ed25519") + _ssh_string(public_key)


def _require_agent_identity(socket_path: str, expected_blob: bytes) -> None:
    response = _ssh_agent_exchange(
        socket_path,
        bytes([SSH_AGENTC_REQUEST_IDENTITIES]),
        5.0,
    )
    if not response:
        raise ValueError("SSH agent returned an empty identity response")
    if response[0] == SSH_AGENT_FAILURE:
        raise ValueError("confirmed SSH signer refused the identity request")
    if response[0] != SSH_AGENT_IDENTITIES_ANSWER or len(response) < 5:
        raise ValueError("SSH agent returned an unexpected identity response")
    count = struct.unpack(">I", response[1:5])[0]
    if count > 128:
        raise ValueError("SSH agent returned too many identities")
    offset = 5
    matched = 0
    for _ in range(count):
        blob, offset = _take_ssh_string(response, offset)
        _comment, offset = _take_ssh_string(response, offset)
        if blob == expected_blob:
            matched += 1
    if offset != len(response):
        raise ValueError("SSH agent identity response contains trailing bytes")
    if matched != 1:
        raise ValueError("trusted Owner key is not one unique active SSH agent identity")


def _sign_with_confirmed_ssh_agent(
    canonical_receipt: bytes,
    public_key: bytes,
    *,
    socket_path: str,
) -> bytes:
    """Ask a separately configured confirmation-constrained SSH agent to sign."""
    key_blob = _ed25519_key_blob(public_key)
    _require_agent_identity(socket_path, key_blob)
    request = (
        bytes([SSH2_AGENTC_SIGN_REQUEST])
        + _ssh_string(key_blob)
        + _ssh_string(canonical_receipt)
        + struct.pack(">I", 0)
    )
    response = _ssh_agent_exchange(socket_path, request, 120.0)
    if not response:
        raise ValueError("SSH agent returned an empty signing response")
    if response[0] == SSH_AGENT_FAILURE:
        raise ValueError("Owner declined or the confirmed SSH signer refused the request")
    if response[0] != SSH2_AGENT_SIGN_RESPONSE:
        raise ValueError("SSH agent returned an unexpected signing response")
    signature_blob, offset = _take_ssh_string(response, 1)
    if offset != len(response):
        raise ValueError("SSH agent signing response contains trailing bytes")
    algorithm, offset = _take_ssh_string(signature_blob, 0)
    signature, offset = _take_ssh_string(signature_blob, offset)
    if offset != len(signature_blob) or algorithm != b"ssh-ed25519" or len(signature) != 64:
        raise ValueError("SSH agent did not return one raw Ed25519 signature")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            canonical_receipt,
        )
    except (ValueError, InvalidSignature) as exc:
        raise ValueError("SSH agent signature does not match the trusted Owner key") from exc
    return signature


def approve_product_decision(
    root: Path,
    request_path: str,
    choice: str,
    output: Path,
    *,
    ssh_auth_sock: str | None = None,
    expected_card_sha256: str,
) -> dict[str, Any]:
    """Turn one semantic Owner choice into a verified Ed25519 receipt."""
    _request, card = build_product_approval_card(root, request_path)
    actual_card_sha256 = product_approval_card_sha256(card)
    if (
        not isinstance(expected_card_sha256, str)
        or not secrets.compare_digest(actual_card_sha256, expected_card_sha256)
    ):
        raise ValueError(
            "product approval card changed after Owner display; review the new card"
        )
    options = {
        row["label"]: row["description"]
        for row in card["options"]
        if isinstance(row, dict)
        and isinstance(row.get("label"), str)
        and isinstance(row.get("description"), str)
    }
    if choice not in options:
        raise ValueError("Owner choice must name one option on the validated approval card")
    if choice != card["recommended"]:
        return {
            "state": "DECLINED",
            "decision_id": card["decision_id"],
            "selected_option": choice,
            "receipt_written": False,
        }
    approver_id = card["approver_id"]
    valid_days = card["valid_days"]
    public_key = _trusted_owner_public_key(root, approver_id)
    if not secrets.compare_digest(
        hashlib.sha256(public_key).hexdigest(),
        card["approver_key_sha256"],
    ):
        raise ValueError("trusted Owner key changed after Owner display")
    binding = _trusted_approver_domain(root, approver_id)
    if (
        binding["repository_id"] != card["repository_id"]
        or binding["trust_domain"] != card["trust_domain"]
    ):
        raise ValueError("trusted Owner audience changed after Owner display")
    assumptions, assumptions_sha256 = _assumption_rows(
        root,
        card["assumption_paths"],
    )
    if (
        assumptions != card["assumptions"]
        or not secrets.compare_digest(
            assumptions_sha256,
            card["assumptions_sha256"],
        )
    ):
        raise ValueError(
            "product approval assumptions changed before signing; review the new card"
        )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    receipt = {
        "decision_id": card["decision_id"],
        "summary": f"Approved option {choice}: {options[choice]}",
        "scope": card["scope_of_approval"],
        "assumptions": assumptions,
        "assumptions_sha256": assumptions_sha256,
        "reopen_condition": "scope_or_assumptions_change",
        "approved_by": approver_id,
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(days=valid_days)).isoformat().replace(
            "+00:00", "Z"
        ),
        "nonce": secrets.token_urlsafe(24),
    }
    canonical = _canonical_receipt(receipt)
    socket_path = ssh_auth_sock if ssh_auth_sock is not None else os.environ.get("SSH_AUTH_SOCK", "")
    signature = _sign_with_confirmed_ssh_agent(
        canonical,
        public_key,
        socket_path=socket_path,
    )
    envelope = {
        "schema_version": "1.0",
        "algorithm": "ed25519",
        "receipt": receipt,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    verified, receipt_sha256 = _verify_product_envelope(root, envelope)
    if verified != receipt:
        raise ValueError("signed Owner receipt changed during local verification")
    write_new_regular_file(
        output,
        json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
        "signed product approval receipt",
        mode=0o600,
        directory_mode=0o700,
    )
    return {
        "state": "APPROVED",
        "decision_id": receipt["decision_id"],
        "selected_option": choice,
        "approved_by": approver_id,
        "expires_at": receipt["expires_at"],
        "receipt_sha256": receipt_sha256,
        "receipt_written": True,
        "output": str(output),
    }
