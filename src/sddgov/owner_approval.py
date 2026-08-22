"""Owner-facing product approval without exposing signing keys to the Agent."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import socket
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .autonomy import (
    _canonical_receipt,
    _read_repository_regular_file,
    _trusted_approver,
    _verify_product_envelope,
    evaluate_escalation,
)
from .fs_security import write_new_regular_file


MAX_APPROVAL_REQUEST_BYTES = 1024 * 1024
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


def _safe_relative_path(value: str, label: str) -> PurePosixPath:
    pure = PurePosixPath(value)
    if (
        not value
        or "\\" in value
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
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must contain one UTF-8 JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain one JSON object")
    return value


def _assumption_rows(root: Path, values: list[str]) -> tuple[list[dict[str, str]], str]:
    if not values:
        raise ValueError("at least one decision assumption artifact is required")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        pure = _safe_relative_path(value, "decision assumption")
        if value in seen:
            raise ValueError("decision assumption paths must be unique")
        seen.add(value)
        raw = _read_repository_regular_file(
            root,
            pure,
            max_bytes=MAX_APPROVAL_REQUEST_BYTES,
        )
        rows.append({"path": value, "sha256": hashlib.sha256(raw).hexdigest()})
    digest = hashlib.sha256(_canonical_json(rows)).hexdigest()
    return rows, digest


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
    return request, card


def render_product_approval_card(card: dict[str, Any]) -> str:
    """Render only the product meaning an Owner must decide, never machine digests."""
    options = card.get("options")
    if not isinstance(options, list) or not options:
        raise ValueError("product approval card has no options")
    lines = [
        "SDG OWNER DECISION",
        f"Decision: {card['decision_id']}",
        f"Risk: {card['risk_level']}",
        "",
        "Scope:",
        card["scope_of_approval"],
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
    return "\n".join(lines) + "\n"


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
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
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
        connection.close()


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
    assumption_paths: list[str],
    approver_id: str,
    choice: str,
    output: Path,
    *,
    valid_days: int = 30,
    ssh_auth_sock: str | None = None,
) -> dict[str, Any]:
    """Turn one semantic Owner choice into a verified Ed25519 receipt."""
    _request, card = build_product_approval_card(root, request_path)
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
    if not isinstance(valid_days, int) or not 1 <= valid_days <= 366:
        raise ValueError("product approval validity must be between 1 and 366 days")
    approver = _trusted_approver(root, approver_id)
    try:
        public_key = base64.b64decode(approver["public_key"], validate=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("trusted Owner public key is invalid") from exc
    assumptions, assumptions_sha256 = _assumption_rows(root, assumption_paths)
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
