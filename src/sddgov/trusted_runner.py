from __future__ import annotations

import array
import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .autonomy import evaluate_escalation, import_operation_approval

_ACTION_ID = "AF25-HERMES-OPENAI-API-LIVE-UAT-L3-001"
_OFFICIAL_ENDPOINT = "https://api.openai.com/v1"
_MANAGED_PATHS = frozenset(
    {
        "agent/relay_llm.py",
        "agent/auxiliary_client.py",
        "hermes_cli/auth.py",
        "gateway/platforms/api_server.py",
        "agent/transports/codex.py",
    }
)
_SOURCE_MANIFEST_PATH = ".agent-factory/source-tree-manifest.json"
_ORIGINAL_SOURCE_PREFIX = ".agent-factory/original/"
_EXPECTED_CONTAINMENT_PROFILE = {
    "contract_version": "0.1",
    "hermes_version": "0.20.4",
    "source_revision": "f43eabee5f36e11448086ee8ee17c499958e81bf",
    "source_hashes": {
        "agent/auxiliary_client.py": (
            "ecd2bfa8eda3669637e2817691daf72d81b4abcac0f9b9f5a486d7cd6c3aba24"
        ),
        "agent/relay_llm.py": (
            "02d7d287b9a314592dd6247baf40aa09e442aaab60f1ade6c5edbc9eaef6b9e3"
        ),
        "agent/transports/codex.py": (
            "b91f9e2679a17cdfc74d565ee2190afbc81ca73aaa35adbff9c37ae3d2807b0e"
        ),
        "gateway/platforms/api_server.py": (
            "204fa3e857dc50c032e084f2e8ebd864ea3ebbac80891f65ad85760e92edfeda"
        ),
        "hermes_cli/auth.py": (
            "59801d820f0106cf9342f6b80558b6c0a683bee5985c75944bb7ca8705a6fa7c"
        ),
    },
    "provider": "openai-api",
    "model": "gpt-5.6-sol",
    "max_inference_calls": 1,
    "max_output_tokens": 1_000,
}
_EXPECTED_ROUTE_PROFILE = {
    "contract_version": "0.1",
    "containment_profile_hash": (
        "sha256:9f276ddbe0a6fc57e662ebc8dc7fe6542dea7d6af9b34f5ceec977114510d2de"
    ),
    "hermes_version": "0.20.4",
    "source_revision": "f43eabee5f36e11448086ee8ee17c499958e81bf",
    "source_tree_hash": (
        "sha256:3865fb7970e7f2ee2c0eb963654755fa72b785a5fe970a79cd51adc93e7647c8"
    ),
    "provider": "openai-api",
    "model": "gpt-5.6-sol",
    "endpoint": "https://api.openai.com/v1",
    "access_method": "api",
    "credential_env_var": "OPENAI_API_KEY",
    "max_input_bytes": 4_096,
    "max_output_tokens": 1_000,
    "max_inference_calls": 1,
    "cost_control_mode": "metered_hard_cap",
    "max_cost_usd": "0.25",
    "maximum_cost_usd": "0.05048",
    "input_price_per_million_usd": "5",
    "output_price_per_million_usd": "30",
    "price_snapshot_date": "2026-08-23",
    "offline_only": True,
}
# Python builds may omit the Linux sealing constants even when the running
# kernel implements memfd sealing.  These values are stable Linux UAPI values.
_F_GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
_F_SEAL_SEAL = getattr(fcntl, "F_SEAL_SEAL", 0x0001)
_F_SEAL_SHRINK = getattr(fcntl, "F_SEAL_SHRINK", 0x0002)
_F_SEAL_GROW = getattr(fcntl, "F_SEAL_GROW", 0x0004)
_F_SEAL_WRITE = getattr(fcntl, "F_SEAL_WRITE", 0x0008)
_REQUIRED_SEALS = _F_SEAL_WRITE | _F_SEAL_GROW | _F_SEAL_SHRINK | _F_SEAL_SEAL
_MAX_REQUEST_BYTES = 128 * 1024
_MAX_SECRET_BYTES = 512
_MAX_CHILD_ARTIFACT_BYTES = 1024 * 1024
_MAX_INPUT_BYTES = 4_096
_MAX_OUTPUT_TOKENS = 1_000
_MAX_INFERENCE_CALLS = 1
_MAX_COST_USD = Decimal("0.25")
_MAX_DURATION_SECONDS = 120
_CHILD_WAIT_TIMEOUT_SECONDS = _MAX_DURATION_SECONDS
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_INHERITED_ENV_ALLOWLIST = ("LANG", "LC_ALL", "SSL_CERT_DIR", "SSL_CERT_FILE")


class TrustedRunnerViolation(RuntimeError):
    """Fail-closed trusted Runner error containing only a safe reason code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_hash(value: Any) -> str:
    return _sha256(_canonical_bytes(value))


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrustedRunnerViolation(f"{label}_invalid")
    return value


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TrustedRunnerViolation("json_duplicate_key_denied")
        result[key] = value
    return result


def _strict_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_object)
    except TrustedRunnerViolation:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustedRunnerViolation(f"{label}_invalid") from exc
    if not isinstance(value, dict):
        raise TrustedRunnerViolation(f"{label}_invalid")
    return value


def _stable_read_regular(
    path: Path,
    *,
    label: str,
    expected_uid: int | None = None,
    expected_mode: int | None = None,
    maximum_bytes: int | None = None,
) -> tuple[bytes, os.stat_result]:
    candidate = path.expanduser().absolute()
    try:
        before = candidate.lstat()
    except OSError as exc:
        raise TrustedRunnerViolation(f"{label}_unavailable") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise TrustedRunnerViolation(f"{label}_not_private_regular")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise TrustedRunnerViolation(f"{label}_unavailable") from exc
    try:
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise TrustedRunnerViolation(f"{label}_identity_changed")
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise TrustedRunnerViolation(f"{label}_not_private_regular")
        if expected_uid is not None and opened.st_uid != expected_uid:
            raise TrustedRunnerViolation(f"{label}_owner_invalid")
        if expected_mode is not None and stat.S_IMODE(opened.st_mode) != expected_mode:
            raise TrustedRunnerViolation(f"{label}_permissions_invalid")
        read_limit = None if maximum_bytes is None else maximum_bytes + 1
        chunks: list[bytes] = []
        total = 0
        while read_limit is None or total < read_limit:
            size = 1024 * 1024 if read_limit is None else min(64 * 1024, read_limit - total)
            if size <= 0:
                break
            chunk = os.read(descriptor, size)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after_fd = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = candidate.lstat()
    except OSError as exc:
        raise TrustedRunnerViolation(f"{label}_identity_changed") from exc
    identity = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    if identity(opened) != identity(after_fd) or identity(opened) != identity(after_path):
        raise TrustedRunnerViolation(f"{label}_identity_changed")
    raw = b"".join(chunks)
    if maximum_bytes is not None and len(raw) > maximum_bytes:
        raise TrustedRunnerViolation(f"{label}_too_large")
    if len(raw) != opened.st_size:
        raise TrustedRunnerViolation(f"{label}_read_incomplete")
    return raw, opened


def _stable_read_secret(
    path: Path,
    *,
    expected_uid: int,
    maximum_bytes: int,
) -> bytearray:
    candidate = path.expanduser().absolute()
    buffer = bytearray()
    try:
        before = candidate.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise TrustedRunnerViolation("credential_source_not_private_regular")
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor = os.open(candidate, flags)
        try:
            opened = os.fstat(descriptor)
            if (
                (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
                or not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or opened.st_uid != expected_uid
                or stat.S_IMODE(opened.st_mode) != 0o600
                or opened.st_size <= 0
                or opened.st_size > maximum_bytes
            ):
                raise TrustedRunnerViolation("credential_source_metadata_invalid")
            buffer = bytearray(opened.st_size)
            offset = 0
            while offset < len(buffer):
                read = os.readv(descriptor, [memoryview(buffer)[offset:]])
                if read <= 0:
                    raise TrustedRunnerViolation("credential_source_read_incomplete")
                offset += read
            after_fd = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after_path = candidate.lstat()
        identity = lambda item: (
            item.st_dev,
            item.st_ino,
            item.st_mode,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )
        if identity(opened) != identity(after_fd) or identity(opened) != identity(after_path):
            raise TrustedRunnerViolation("credential_source_identity_changed")
        return buffer
    except TrustedRunnerViolation:
        buffer[:] = b"\x00" * len(buffer)
        raise
    except OSError as exc:
        buffer[:] = b"\x00" * len(buffer)
        raise TrustedRunnerViolation("credential_source_unavailable") from exc


def _private_directory(path: Path, label: str, expected_uid: int) -> Path:
    candidate = path.expanduser().absolute()
    try:
        before = candidate.lstat()
    except OSError as exc:
        raise TrustedRunnerViolation(f"{label}_unavailable") from exc
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISDIR(before.st_mode)
        or before.st_uid != expected_uid
        or stat.S_IMODE(before.st_mode) != 0o700
    ):
        raise TrustedRunnerViolation(f"{label}_invalid")
    return candidate.resolve(strict=True)


def _outside_tmp(path: Path, label: str) -> None:
    candidate = path.expanduser().absolute()
    if candidate == Path("/tmp") or candidate.is_relative_to(Path("/tmp")):
        raise TrustedRunnerViolation(f"production_{label}_under_tmp")


def _production_directory_chain(path: Path, label: str, service_uid: int) -> None:
    cursor = path.expanduser().absolute()
    while True:
        try:
            info = cursor.lstat()
        except OSError as exc:
            raise TrustedRunnerViolation(f"production_{label}_ancestor_unavailable") from exc
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid not in {0, service_uid}
            or info.st_mode & 0o022
        ):
            raise TrustedRunnerViolation(f"production_{label}_ancestor_invalid")
        if cursor.parent == cursor:
            break
        cursor = cursor.parent


@dataclass(frozen=True, slots=True, repr=False)
class TrustedRunnerBootstrap:
    runner_id: str
    mode: str
    service_uid: int
    allowed_client_uids: tuple[int, ...]
    state_root: Path
    trusted_approvers_file: Path
    result_private_key: Path
    result_public_key: str
    runtime_executable: Path
    runtime_sha256: str
    runtime_argv: tuple[str, ...]
    credential_ref: str
    credential_path: Path
    credential_sha256: str
    credential_binding_hash: str
    isolation_parent: Path
    bootstrap_path: Path

    @classmethod
    def load(cls, path: str | Path) -> TrustedRunnerBootstrap:
        bootstrap_path = Path(path).expanduser().absolute()
        raw, _ = _stable_read_regular(
            bootstrap_path,
            label="runner_bootstrap",
            expected_uid=os.geteuid(),
            expected_mode=0o600,
            maximum_bytes=64 * 1024,
        )
        data = _strict_json_bytes(raw, "runner_bootstrap")
        required = {
            "schema_version",
            "runner_id",
            "mode",
            "service_uid",
            "allowed_client_uids",
            "state_root",
            "trusted_approvers_file",
            "result_private_key",
            "result_public_key",
            "runtime_executable",
            "runtime_sha256",
            "runtime_argv",
            "credential_ref",
            "credential_path",
            "credential_sha256",
            "credential_binding_hash",
            "isolation_parent",
        }
        if set(data) != required or data.get("schema_version") != "0.1":
            raise TrustedRunnerViolation("runner_bootstrap_contract_invalid")
        if not isinstance(data.get("runner_id"), str) or not data["runner_id"].strip():
            raise TrustedRunnerViolation("runner_id_invalid")
        if data.get("mode") not in {"production", "rehearsal"}:
            raise TrustedRunnerViolation("runner_mode_invalid")
        service_uid = data.get("service_uid")
        clients = data.get("allowed_client_uids")
        if (
            not isinstance(service_uid, int)
            or isinstance(service_uid, bool)
            or service_uid < 0
            or not isinstance(clients, list)
            or not clients
            or any(
                not isinstance(uid, int) or isinstance(uid, bool) or uid < 0
                for uid in clients
            )
            or len(set(clients)) != len(clients)
        ):
            raise TrustedRunnerViolation("runner_uid_policy_invalid")
        runtime_argv = data.get("runtime_argv")
        if (
            not isinstance(runtime_argv, list)
            or not runtime_argv
            or any(not isinstance(value, str) or not value for value in runtime_argv)
        ):
            raise TrustedRunnerViolation("runtime_argv_invalid")
        for value in runtime_argv:
            braces = "{" in value or "}" in value
            if braces and value not in {
                "{bundle_fd_path}",
                "{hermes_home}",
                "{input_path}",
                "{result_path}",
            }:
                raise TrustedRunnerViolation("runtime_argv_placeholder_invalid")
        if (
            not isinstance(data.get("credential_ref"), str)
            or not data["credential_ref"].startswith("secret-ref://")
        ):
            raise TrustedRunnerViolation("credential_ref_invalid")
        for key in ("runtime_sha256", "credential_sha256", "credential_binding_hash"):
            _require_sha256(data.get(key), key)
        public_key = data.get("result_public_key")
        try:
            public_bytes = base64.b64decode(public_key, validate=True)
        except (TypeError, ValueError, binascii.Error) as exc:
            raise TrustedRunnerViolation("result_public_key_invalid") from exc
        if len(public_bytes) != 32:
            raise TrustedRunnerViolation("result_public_key_invalid")
        bootstrap = cls(
            runner_id=data["runner_id"],
            mode=data["mode"],
            service_uid=service_uid,
            allowed_client_uids=tuple(clients),
            state_root=Path(data["state_root"]).expanduser().absolute(),
            trusted_approvers_file=Path(data["trusted_approvers_file"])
            .expanduser()
            .absolute(),
            result_private_key=Path(data["result_private_key"]).expanduser().absolute(),
            result_public_key=public_key,
            runtime_executable=Path(data["runtime_executable"]).expanduser().absolute(),
            runtime_sha256=data["runtime_sha256"],
            runtime_argv=tuple(runtime_argv),
            credential_ref=data["credential_ref"],
            credential_path=Path(data["credential_path"]).expanduser().absolute(),
            credential_sha256=data["credential_sha256"],
            credential_binding_hash=data["credential_binding_hash"],
            isolation_parent=Path(data["isolation_parent"]).expanduser().absolute(),
            bootstrap_path=bootstrap_path,
        )
        bootstrap._validate()
        return bootstrap

    def _validate(self) -> None:
        current_uid = os.geteuid()
        if self.service_uid != current_uid:
            raise TrustedRunnerViolation("runner_service_uid_mismatch")
        if self.mode == "production":
            raise TrustedRunnerViolation("production_cgroup_containment_required")
        if self.mode == "production" and (
            current_uid == 0 or current_uid in self.allowed_client_uids
        ):
            raise TrustedRunnerViolation("production_uid_separation_required")
        _private_directory(self.state_root, "runner_state_root", current_uid)
        _stable_read_regular(
            self.trusted_approvers_file,
            label="trusted_approvers",
            expected_uid=current_uid,
            expected_mode=0o600,
            maximum_bytes=64 * 1024,
        )
        _stable_read_regular(
            self.result_private_key,
            label="result_private_key",
            expected_uid=current_uid,
            expected_mode=0o600,
            maximum_bytes=32,
        )
        credential_info = self.credential_path.lstat()
        if (
            stat.S_ISLNK(credential_info.st_mode)
            or not stat.S_ISREG(credential_info.st_mode)
            or credential_info.st_uid != current_uid
            or credential_info.st_nlink != 1
            or stat.S_IMODE(credential_info.st_mode) != 0o600
        ):
            raise TrustedRunnerViolation("credential_source_metadata_invalid")
        isolation = _private_directory(
            self.isolation_parent, "isolation_parent", current_uid
        )
        object.__setattr__(self, "isolation_parent", isolation)
        runtime_raw, runtime_info = _stable_read_regular(
            self.runtime_executable,
            label="runtime_executable",
        )
        if runtime_info.st_uid not in {0, current_uid} or runtime_info.st_mode & 0o022:
            raise TrustedRunnerViolation("runtime_executable_permissions_invalid")
        if _sha256(runtime_raw) != self.runtime_sha256:
            raise TrustedRunnerViolation("runtime_executable_hash_mismatch")
        expected_binding = _canonical_hash(
            {
                "runner_id": self.runner_id,
                "credential_ref": self.credential_ref,
                "credential_sha256": self.credential_sha256,
            }
        )
        if self.credential_binding_hash != expected_binding:
            raise TrustedRunnerViolation("credential_binding_invalid")
        if self.mode == "production":
            for value, label, is_directory in (
                (self.bootstrap_path, "bootstrap", False),
                (self.state_root, "state", True),
                (self.trusted_approvers_file, "trust", False),
                (self.result_private_key, "signing_key", False),
                (self.runtime_executable, "runtime", False),
                (self.credential_path, "credential", False),
                (self.isolation_parent, "isolation", True),
            ):
                _outside_tmp(value, label)
                _production_directory_chain(
                    value if is_directory else value.parent,
                    label,
                    self.service_uid,
                )

    def _authority_hash(self) -> str:
        raw, _ = _stable_read_regular(
            self.trusted_approvers_file,
            label="trusted_approvers",
            expected_uid=self.service_uid,
            expected_mode=0o600,
            maximum_bytes=64 * 1024,
        )
        return _canonical_hash(_strict_json_bytes(raw, "trusted_approvers"))

    def descriptor(self) -> dict[str, str]:
        runner_identity = _canonical_hash(
            {
                "contract_version": "0.1",
                "runner_id": self.runner_id,
                "service_uid": self.service_uid,
                "result_public_key": self.result_public_key,
            }
        )
        runtime_identity = _canonical_hash(
            {
                "runtime_sha256": self.runtime_sha256,
                "runtime_argv": list(self.runtime_argv),
            }
        )
        isolation_policy = _canonical_hash(
            {
                "mode": self.mode,
                "isolation_parent_binding": _sha256(
                    str(self.isolation_parent).encode("utf-8")
                ),
                "max_duration_seconds": _MAX_DURATION_SECONDS,
                "cleanup": "term-kill-zeroize-unlink-rmtree-v1",
            }
        )
        launch_contract = _canonical_hash(
            {
                "runtime_identity_hash": runtime_identity,
                "isolation_policy_hash": isolation_policy,
                "provider": "openai-api",
                "model": "gpt-5.6-sol",
                "endpoint": _OFFICIAL_ENDPOINT,
                "max_input_bytes": _MAX_INPUT_BYTES,
                "max_output_tokens": _MAX_OUTPUT_TOKENS,
                "max_inference_calls": _MAX_INFERENCE_CALLS,
                "max_cost_usd": str(_MAX_COST_USD),
                "max_duration_seconds": _MAX_DURATION_SECONDS,
            }
        )
        return {
            "contract_version": "0.2",
            "runner_identity_hash": runner_identity,
            "approval_authority_identity_hash": self._authority_hash(),
            "credential_binding_hash": self.credential_binding_hash,
            "runtime_identity_hash": runtime_identity,
            "isolation_policy_hash": isolation_policy,
            "launch_contract_hash": launch_contract,
            "approval_protocol": "sddgov-ed25519-exact-operation-v1",
            "credential_protocol": "sealed-secret-fd-v1",
        }


@dataclass(frozen=True, slots=True)
class _ValidatedRequest:
    request: Mapping[str, Any]
    operation: Mapping[str, Any]
    operation_id: str
    plan_hash: str
    approval_id: str
    approval_envelope: Mapping[str, Any]
    input_payload: bytes


class TrustedRunner:
    """One-shot dedicated-UID Runner; never exposes credential material to caller."""

    def __init__(self, bootstrap: TrustedRunnerBootstrap) -> None:
        if not isinstance(bootstrap, TrustedRunnerBootstrap):
            raise TypeError("bootstrap must be TrustedRunnerBootstrap")
        self.bootstrap = bootstrap

    @classmethod
    def from_path(cls, path: str | Path) -> TrustedRunner:
        return cls(TrustedRunnerBootstrap.load(path))

    def _validate_request(self, request: Mapping[str, Any]) -> _ValidatedRequest:
        required = {
            "schema_version",
            "operation",
            "capsule",
            "sealed_bundle_delivery",
            "approval_required",
            "credential_delivery",
            "approval_id",
            "approval_envelope",
            "input_payload_b64",
        }
        if set(request) != required or request.get("schema_version") != "0.1":
            raise TrustedRunnerViolation("runner_request_contract_invalid")
        if (
            request.get("sealed_bundle_delivery") != "inherited-sealed-fd"
            or request.get("approval_required") is not True
            or request.get("credential_delivery") != "external-runner-private-fd"
        ):
            raise TrustedRunnerViolation("runner_request_delivery_invalid")
        operation = request.get("operation")
        capsule = request.get("capsule")
        if not isinstance(operation, dict) or not isinstance(capsule, dict):
            raise TrustedRunnerViolation("runner_request_contract_invalid")
        operation_required = {
            "contract_version",
            "action_id",
            "credential_ref",
            "input_payload_hash",
            "launch_contract_hash",
            "sealed_bundle_hash",
            "sealed_bundle_size_bytes",
            "sealed_bundle_entry_count",
            "source_tree_hash",
            "managed_hashes",
            "external_bindings",
            "route_profile_hash",
            "containment_profile_hash",
            "route_profile",
            "containment_profile",
            "provider",
            "model",
            "endpoint",
            "max_input_bytes",
            "max_output_tokens",
            "max_inference_calls",
            "max_cost_usd",
            "max_duration_seconds",
            "gate_mode",
            "rehearsal_only",
            "tool_policy",
            "approval_subagents",
            "auxiliary_inference",
            "promotion",
            "gate_enforce",
            "deployment",
            "external_trusted_runner_required",
            "operation_id",
        }
        if set(operation) != operation_required or operation.get("contract_version") != "0.3":
            raise TrustedRunnerViolation("operation_contract_invalid")
        expected_values = {
            "action_id": _ACTION_ID,
            "credential_ref": self.bootstrap.credential_ref,
            "launch_contract_hash": self.bootstrap.descriptor()["launch_contract_hash"],
            "provider": "openai-api",
            "model": "gpt-5.6-sol",
            "endpoint": _OFFICIAL_ENDPOINT,
            "max_input_bytes": _MAX_INPUT_BYTES,
            "max_output_tokens": _MAX_OUTPUT_TOKENS,
            "max_inference_calls": _MAX_INFERENCE_CALLS,
            "max_cost_usd": str(_MAX_COST_USD),
            "max_duration_seconds": _MAX_DURATION_SECONDS,
            "gate_mode": "shadow",
            "rehearsal_only": self.bootstrap.mode == "rehearsal",
            "tool_policy": "zero",
            "approval_subagents": "denied",
            "auxiliary_inference": "denied",
            "promotion": False,
            "gate_enforce": False,
            "deployment": False,
            "external_trusted_runner_required": True,
        }
        if any(operation.get(key) != value for key, value in expected_values.items()):
            raise TrustedRunnerViolation("operation_policy_mismatch")
        containment_profile = operation.get("containment_profile")
        route_profile = operation.get("route_profile")
        if not isinstance(containment_profile, dict) or set(
            containment_profile
        ) != set(_EXPECTED_CONTAINMENT_PROFILE):
            raise TrustedRunnerViolation("containment_profile_binding_mismatch")
        expected_containment_policy = dict(_EXPECTED_CONTAINMENT_PROFILE)
        source_hashes = containment_profile.get("source_hashes")
        expected_containment_policy["source_hashes"] = source_hashes
        if (
            containment_profile != expected_containment_policy
            or not isinstance(source_hashes, dict)
            or set(source_hashes) != _MANAGED_PATHS
            or any(
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in source_hashes.values()
            )
            or operation.get("containment_profile_hash")
            != _canonical_hash(containment_profile)
            or (
                self.bootstrap.mode == "production"
                and containment_profile != _EXPECTED_CONTAINMENT_PROFILE
            )
        ):
            raise TrustedRunnerViolation("containment_profile_binding_mismatch")
        if not isinstance(route_profile, dict) or set(route_profile) != set(
            _EXPECTED_ROUTE_PROFILE
        ):
            raise TrustedRunnerViolation("route_profile_binding_mismatch")
        expected_route_policy = dict(_EXPECTED_ROUTE_PROFILE)
        expected_route_policy["containment_profile_hash"] = operation.get(
            "containment_profile_hash"
        )
        expected_route_policy["source_tree_hash"] = operation.get("source_tree_hash")
        if (
            route_profile != expected_route_policy
            or operation.get("route_profile_hash") != _canonical_hash(route_profile)
            or route_profile.get("containment_profile_hash")
            != operation.get("containment_profile_hash")
            or route_profile.get("source_tree_hash")
            != operation.get("source_tree_hash")
            or (
                self.bootstrap.mode == "production"
                and route_profile != _EXPECTED_ROUTE_PROFILE
            )
        ):
            raise TrustedRunnerViolation("route_profile_binding_mismatch")
        bindings = operation.get("external_bindings")
        if bindings != self.bootstrap.descriptor():
            raise TrustedRunnerViolation("operation_external_bindings_mismatch")
        for key in (
            "input_payload_hash",
            "launch_contract_hash",
            "sealed_bundle_hash",
            "source_tree_hash",
            "route_profile_hash",
            "containment_profile_hash",
        ):
            _require_sha256(operation.get(key), key)
        if (
            not isinstance(operation.get("sealed_bundle_size_bytes"), int)
            or isinstance(operation["sealed_bundle_size_bytes"], bool)
            or operation["sealed_bundle_size_bytes"] <= 0
            or not isinstance(operation.get("sealed_bundle_entry_count"), int)
            or isinstance(operation["sealed_bundle_entry_count"], bool)
            or operation["sealed_bundle_entry_count"] <= 0
        ):
            raise TrustedRunnerViolation("sealed_bundle_shape_invalid")
        managed = operation.get("managed_hashes")
        if not isinstance(managed, dict) or set(managed) != _MANAGED_PATHS:
            raise TrustedRunnerViolation("managed_hashes_invalid")
        for path, digest in managed.items():
            _require_sha256(digest, f"managed_hash_{_sha256(path.encode())[-8:]}")
        try:
            payload = base64.b64decode(request.get("input_payload_b64"), validate=True)
        except (TypeError, ValueError, binascii.Error) as exc:
            raise TrustedRunnerViolation("input_payload_invalid") from exc
        if not payload or len(payload) > _MAX_INPUT_BYTES:
            raise TrustedRunnerViolation("input_payload_size_invalid")
        if _sha256(payload) != operation["input_payload_hash"]:
            raise TrustedRunnerViolation("input_payload_hash_mismatch")
        operation_id = operation.get("operation_id")
        if not isinstance(operation_id, str):
            raise TrustedRunnerViolation("operation_id_invalid")
        canonical_operation = dict(operation)
        canonical_operation.pop("operation_id")
        plan_hash = _canonical_hash(canonical_operation)
        expected_operation_id = f"{_ACTION_ID}@{plan_hash.removeprefix('sha256:')}"
        if operation_id != expected_operation_id:
            raise TrustedRunnerViolation("operation_id_mismatch")
        capsule_required = {
            "contract_version",
            "operation_id",
            "plan_hash",
            "sealed_bundle_hash",
            "external_bindings_hash",
            "environment_hash",
            "rehearsal_only",
            "credential_material_included",
            "authorization_consumed",
            "launch_permitted",
            "runtime_started",
            "inference_applied",
            "promotion_applied",
            "gate_enforce_applied",
            "deployment_applied",
        }
        if (
            set(capsule) != capsule_required
            or capsule.get("contract_version") != "0.3"
            or capsule.get("operation_id") != operation_id
            or capsule.get("plan_hash") != plan_hash
            or capsule.get("sealed_bundle_hash") != operation["sealed_bundle_hash"]
            or capsule.get("external_bindings_hash") != _canonical_hash(bindings)
            or capsule.get("rehearsal_only") != operation["rehearsal_only"]
            or any(
                capsule.get(key) is not False
                for key in (
                    "credential_material_included",
                    "authorization_consumed",
                    "launch_permitted",
                    "runtime_started",
                    "inference_applied",
                    "promotion_applied",
                    "gate_enforce_applied",
                    "deployment_applied",
                )
            )
        ):
            raise TrustedRunnerViolation("capsule_contract_mismatch")
        _require_sha256(capsule.get("environment_hash"), "environment_hash")
        approval_id = request.get("approval_id")
        envelope = request.get("approval_envelope")
        if not isinstance(approval_id, str) or not approval_id.strip() or not isinstance(envelope, dict):
            raise TrustedRunnerViolation("approval_envelope_invalid")
        receipt = envelope.get("receipt")
        if (
            not isinstance(receipt, dict)
            or receipt.get("approval_id") != approval_id
            or receipt.get("operation_id") != operation_id
        ):
            raise TrustedRunnerViolation("approval_operation_mismatch")
        return _ValidatedRequest(
            request=request,
            operation=operation,
            operation_id=operation_id,
            plan_hash=plan_hash,
            approval_id=approval_id,
            approval_envelope=envelope,
            input_payload=payload,
        )

    def _verify_bundle(self, descriptor: int, operation: Mapping[str, Any]) -> None:
        try:
            before = os.fstat(descriptor)
            seals = fcntl.fcntl(descriptor, _F_GET_SEALS)
            link = os.readlink(f"/proc/self/fd/{descriptor}")
        except OSError as exc:
            raise TrustedRunnerViolation("sealed_bundle_fd_invalid") from exc
        if not stat.S_ISREG(before.st_mode) or "memfd:" not in link:
            raise TrustedRunnerViolation("sealed_bundle_not_memfd")
        if seals & _REQUIRED_SEALS != _REQUIRED_SEALS:
            raise TrustedRunnerViolation("sealed_bundle_seals_missing")
        if before.st_size != operation["sealed_bundle_size_bytes"]:
            raise TrustedRunnerViolation("sealed_bundle_size_mismatch")
        digest = hashlib.sha256()
        offset = 0
        while offset < before.st_size:
            chunk = os.pread(descriptor, min(1024 * 1024, before.st_size - offset), offset)
            if not chunk:
                raise TrustedRunnerViolation("sealed_bundle_read_incomplete")
            digest.update(chunk)
            offset += len(chunk)
        after = os.fstat(descriptor)
        if (
            (before.st_dev, before.st_ino, before.st_size)
            != (after.st_dev, after.st_ino, after.st_size)
            or "sha256:" + digest.hexdigest() != operation["sealed_bundle_hash"]
        ):
            raise TrustedRunnerViolation("sealed_bundle_identity_mismatch")
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    entries = archive.infolist()
                    names = [entry.filename for entry in entries]
                    if len(entries) != operation["sealed_bundle_entry_count"]:
                        raise TrustedRunnerViolation("sealed_bundle_entry_count_mismatch")
                    if len(names) != len(set(names)):
                        raise TrustedRunnerViolation("sealed_bundle_duplicate_entry")
                    by_name = {entry.filename: entry for entry in entries}
                    total_uncompressed = 0
                    for entry in entries:
                        name = entry.filename
                        path = Path(name)
                        if (
                            not name
                            or "\x00" in name
                            or "\\" in name
                            or path.is_absolute()
                            or ".." in path.parts
                        ):
                            raise TrustedRunnerViolation("sealed_bundle_path_invalid")
                        if (
                            entry.is_dir()
                            or entry.compress_type != zipfile.ZIP_STORED
                            or entry.flag_bits & 0x1
                        ):
                            raise TrustedRunnerViolation("sealed_bundle_entry_invalid")
                        total_uncompressed += entry.file_size
                    if total_uncompressed > before.st_size:
                        raise TrustedRunnerViolation("sealed_bundle_size_amplification")
                    try:
                        manifest_raw = archive.read(_SOURCE_MANIFEST_PATH)
                        manifest = json.loads(
                            manifest_raw.decode("utf-8"),
                            object_pairs_hook=_no_duplicate_object,
                        )
                    except TrustedRunnerViolation:
                        raise
                    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise TrustedRunnerViolation(
                            "source_tree_manifest_invalid"
                        ) from exc
                    if (
                        not isinstance(manifest, list)
                        or not manifest
                        or manifest_raw != _canonical_bytes(manifest)
                    ):
                        raise TrustedRunnerViolation("source_tree_manifest_invalid")
                    source_paths: set[str] = set()
                    expected_names = {_SOURCE_MANIFEST_PATH}
                    for source_entry in manifest:
                        if not isinstance(source_entry, dict) or set(source_entry) != {
                            "path",
                            "kind",
                            "mode",
                            "value_hash",
                        }:
                            raise TrustedRunnerViolation("source_tree_manifest_invalid")
                        source_path = source_entry.get("path")
                        kind = source_entry.get("kind")
                        mode = source_entry.get("mode")
                        path = Path(source_path) if isinstance(source_path, str) else Path()
                        if (
                            not isinstance(source_path, str)
                            or not source_path
                            or "\x00" in source_path
                            or "\\" in source_path
                            or path.is_absolute()
                            or ".." in path.parts
                            or source_path == ".agent-factory"
                            or source_path.startswith(".agent-factory/")
                            or source_path in source_paths
                            or kind not in {"file", "symlink"}
                            or (kind == "file" and mode not in {"100644", "100755"})
                            or (kind == "symlink" and mode != "120000")
                        ):
                            raise TrustedRunnerViolation("source_tree_manifest_invalid")
                        _require_sha256(
                            source_entry.get("value_hash"), "source_tree_value_hash"
                        )
                        source_paths.add(source_path)
                        expected_names.add(source_path)
                        original_name = source_path
                        if source_path in _MANAGED_PATHS:
                            original_name = _ORIGINAL_SOURCE_PREFIX + source_path
                            expected_names.add(original_name)
                            if (
                                source_entry["value_hash"].removeprefix("sha256:")
                                != operation["containment_profile"]["source_hashes"][
                                    source_path
                                ]
                            ):
                                raise TrustedRunnerViolation(
                                    "containment_source_hash_mismatch"
                                )
                        if (
                            original_name not in by_name
                            or _sha256(archive.read(original_name))
                            != source_entry["value_hash"]
                        ):
                            raise TrustedRunnerViolation(
                                "source_tree_content_mismatch"
                            )
                    if (
                        set(names) != expected_names
                        or _canonical_hash(manifest) != operation["source_tree_hash"]
                    ):
                        raise TrustedRunnerViolation("source_tree_binding_mismatch")
                    for name, expected in operation["managed_hashes"].items():
                        if _sha256(archive.read(name)) != expected:
                            raise TrustedRunnerViolation("managed_bundle_hash_mismatch")
            except (KeyError, OSError, zipfile.BadZipFile) as exc:
                raise TrustedRunnerViolation("sealed_bundle_zip_invalid") from exc

    @contextmanager
    def _authority_environment(self, trusted_approvers_file: Path) -> Iterator[None]:
        names = ("SDDGOV_TRUSTED_APPROVERS_FILE", "SDDGOV_TRUSTED_BASE_REF")
        previous = {name: os.environ.get(name) for name in names}
        os.environ["SDDGOV_TRUSTED_APPROVERS_FILE"] = str(trusted_approvers_file)
        os.environ.pop("SDDGOV_TRUSTED_BASE_REF", None)
        try:
            yield
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    @contextmanager
    def _approval_consumption_lock(self) -> Iterator[None]:
        decisions_dir = self.bootstrap.state_root / ".sddgov"
        decisions_dir.mkdir(mode=0o700, exist_ok=True)
        _private_directory(
            decisions_dir,
            "approval_state_directory",
            self.bootstrap.service_uid,
        )
        lock_path = decisions_dir / "trusted-runner-approval.lock"
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor: int | None = None
        try:
            descriptor = os.open(lock_path, flags, 0o600)
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self.bootstrap.service_uid
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise TrustedRunnerViolation("approval_lock_not_private_regular")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except OSError as exc:
            if descriptor is not None:
                os.close(descriptor)
            raise TrustedRunnerViolation("approval_lock_unavailable") from exc
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _consume_approval(self, request: _ValidatedRequest) -> None:
        with self._approval_consumption_lock():
            self._consume_approval_locked(request)

    def _consume_approval_locked(self, request: _ValidatedRequest) -> None:
        decisions_dir = self.bootstrap.state_root / ".sddgov"
        authority_raw, _ = _stable_read_regular(
            self.bootstrap.trusted_approvers_file,
            label="trusted_approvers",
            expected_uid=self.bootstrap.service_uid,
            expected_mode=0o600,
            maximum_bytes=64 * 1024,
        )
        authority_hash = _canonical_hash(
            _strict_json_bytes(authority_raw, "trusted_approvers")
        )
        expected_authority_hash = request.operation["external_bindings"][
            "approval_authority_identity_hash"
        ]
        if authority_hash != expected_authority_hash:
            raise TrustedRunnerViolation("approval_authority_identity_changed")
        authority_snapshot = self.bootstrap.isolation_parent / (
            f".runner-authority-{os.getpid()}-{time.monotonic_ns()}.json"
        )
        self._write_private(authority_snapshot, authority_raw)
        approval_path = decisions_dir / (
            f".runner-approval-{os.getpid()}-{time.monotonic_ns()}.json"
        )
        descriptor = os.open(
            approval_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        try:
            raw = _canonical_bytes(request.approval_envelope)
            remaining = memoryview(raw)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("approval write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        decision_request = {
            "risk_level": "L3",
            "category": "high_risk_operation",
            "effects": {"high_privilege": True},
            "operation_id": request.operation_id,
            "approval_id": request.approval_id,
            "decision_package": {
                "decision_id": request.operation_id,
                "risk_level": "L3",
                "why_human_input_is_required": "The exact operation may read one secret and perform one metered inference.",
                "what_agent_already_verified": [
                    "The sealed bundle and external Runner bindings match the exact operation",
                    "The Runner owns credential access, child lifetime, and rollback",
                ],
                "options": [
                    {"label": "approve", "description": "Run exactly this one-use operation."},
                    {"label": "deny", "description": "Keep the operation blocked."},
                ],
                "recommended": "approve",
                "why": "Only an exact signed receipt can cross the trusted boundary.",
                "impact_if_no_decision": "No credential is opened and no child starts.",
                "scope_of_approval": request.operation_id,
            },
        }
        try:
            with self._authority_environment(authority_snapshot):
                import_operation_approval(self.bootstrap.state_root, approval_path)
                result = evaluate_escalation(self.bootstrap.state_root, decision_request)
        except (ValueError, FileNotFoundError) as exc:
            raise TrustedRunnerViolation("approval_verification_failed") from exc
        finally:
            try:
                approval_path.unlink()
            except FileNotFoundError:
                pass
            try:
                authority_snapshot.unlink()
            except FileNotFoundError:
                pass
        if self.bootstrap._authority_hash() != expected_authority_hash:
            raise TrustedRunnerViolation("approval_authority_identity_changed")
        expected = {
            "state": "CONTINUE",
            "requires_response": False,
            "reason": "fresh_l3_operation_approval_verified",
            "next_action": "continue",
            "approval_id": request.approval_id,
            "operation_id": request.operation_id,
            "approval_consumed": True,
        }
        if result != expected:
            raise TrustedRunnerViolation("approval_not_consumed")

    def _open_credential(self) -> bytearray:
        raw = _stable_read_secret(
            self.bootstrap.credential_path,
            expected_uid=self.bootstrap.service_uid,
            maximum_bytes=_MAX_SECRET_BYTES,
        )
        if _sha256(raw) != self.bootstrap.credential_sha256:
            raw[:] = b"\x00" * len(raw)
            raise TrustedRunnerViolation("credential_source_hash_mismatch")
        if (
            len(raw) < 20
            or not raw.startswith(b"sk-")
            or any(value < 33 or value > 126 for value in raw)
        ):
            raw[:] = b"\x00" * len(raw)
            raise TrustedRunnerViolation("credential_shape_invalid")
        return raw

    def _verify_runtime(self) -> None:
        raw, info = _stable_read_regular(
            self.bootstrap.runtime_executable,
            label="runtime_executable",
        )
        if info.st_uid not in {0, self.bootstrap.service_uid} or info.st_mode & 0o022:
            raise TrustedRunnerViolation("runtime_executable_permissions_invalid")
        if _sha256(raw) != self.bootstrap.runtime_sha256:
            raise TrustedRunnerViolation("runtime_executable_hash_mismatch")

    @staticmethod
    def _write_private(path: Path, raw: bytes) -> None:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        try:
            remaining = memoryview(raw)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("private write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _run_child(
        self,
        request: _ValidatedRequest,
        bundle_fd: int,
        secret: bytearray,
        isolation_root: Path,
    ) -> dict[str, Any]:
        hermes_home = isolation_root / "hermes-home"
        hermes_home.mkdir(mode=0o700)
        input_path = isolation_root / "input.bin"
        result_path = isolation_root / "result.json"
        stdout_path = isolation_root / "stdout.bin"
        stderr_path = isolation_root / "stderr.bin"
        self._write_private(input_path, request.input_payload)
        placeholders = {
            "{bundle_fd_path}": f"/proc/self/fd/{bundle_fd}",
            "{hermes_home}": str(hermes_home),
            "{input_path}": str(input_path),
            "{result_path}": str(result_path),
        }
        runtime_argv = [
            str(self.bootstrap.runtime_executable),
            *[placeholders.get(value, value) for value in self.bootstrap.runtime_argv],
        ]
        argv = [
            sys.executable,
            "-I",
            "-m",
            "sddgov._trusted_exec",
            str(_MAX_CHILD_ARTIFACT_BYTES),
            str(_MAX_SECRET_BYTES),
            "{secret_fd}",
            *runtime_argv,
        ]
        inherited = {
            name: os.environ[name]
            for name in _INHERITED_ENV_ALLOWLIST
            if os.environ.get(name)
        }
        environment = {
            **inherited,
            "PYTHONPATH": f"/proc/self/fd/{bundle_fd}",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "HERMES_HOME": str(hermes_home),
            "AGENT_FACTORY_HERMES_CONTAINMENT": "1",
            "AGENT_FACTORY_ALLOWED_PROVIDER": "openai-api",
            "AGENT_FACTORY_ALLOWED_MODEL": "gpt-5.6-sol",
            "AGENT_FACTORY_MAX_INFERENCE_CALLS": str(_MAX_INFERENCE_CALLS),
            "AGENT_FACTORY_MAX_OUTPUT_TOKENS": str(_MAX_OUTPUT_TOKENS),
            "AGENT_FACTORY_MAX_INPUT_BYTES": str(_MAX_INPUT_BYTES),
            "AGENT_FACTORY_ALLOWED_BASE_URL": _OFFICIAL_ENDPOINT,
            "OPENAI_BASE_URL": _OFFICIAL_ENDPOINT,
            "HERMES_INFERENCE_PROVIDER": "openai-api",
            "HERMES_MODEL": "gpt-5.6-sol",
            "HERMES_MAX_TOKENS": str(_MAX_OUTPUT_TOKENS),
            "AGENT_FACTORY_INPUT_PATH": str(input_path),
            "AGENT_FACTORY_RESULT_PATH": str(result_path),
        }
        if self.bootstrap.mode == "rehearsal":
            environment["AGENT_FACTORY_OFFLINE_ONLY"] = "1"
        started = time.monotonic()
        stdout_fd = os.open(
            stdout_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        stderr_fd = os.open(
            stderr_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        child: subprocess.Popen[bytes] | None = None
        timed_out = False
        if hasattr(os, "pipe2"):
            secret_read_fd, secret_write_fd = os.pipe2(os.O_CLOEXEC)
        else:  # pragma: no cover - Linux production environments expose pipe2.
            secret_read_fd, secret_write_fd = os.pipe()
            os.set_inheritable(secret_read_fd, False)
            os.set_inheritable(secret_write_fd, False)
        try:
            remaining = memoryview(secret)
            while remaining:
                written = os.write(secret_write_fd, remaining)
                if written <= 0:
                    raise TrustedRunnerViolation("credential_pipe_write_failed")
                remaining = remaining[written:]
        finally:
            os.close(secret_write_fd)
        argv[6] = str(secret_read_fd)
        try:
            child = subprocess.Popen(
                argv,
                cwd=isolation_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout_fd,
                stderr=stderr_fd,
                pass_fds=(bundle_fd, secret_read_fd),
                start_new_session=True,
            )
            try:
                return_code = child.wait(timeout=_CHILD_WAIT_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=2)
                return_code = child.returncode
        finally:
            os.close(secret_read_fd)
            os.close(stdout_fd)
            os.close(stderr_fd)
        stdout_raw, _ = _stable_read_regular(
            stdout_path,
            label="child_stdout",
            expected_uid=self.bootstrap.service_uid,
            expected_mode=0o600,
            maximum_bytes=_MAX_CHILD_ARTIFACT_BYTES,
        )
        stderr_raw, _ = _stable_read_regular(
            stderr_path,
            label="child_stderr",
            expected_uid=self.bootstrap.service_uid,
            expected_mode=0o600,
            maximum_bytes=_MAX_CHILD_ARTIFACT_BYTES,
        )
        observation: dict[str, Any] = {
            "runtime_started": child is not None,
            "timed_out": timed_out,
            "return_code": return_code,
            "stdout_hash": _sha256(stdout_raw),
            "stderr_hash": _sha256(stderr_raw),
            "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
            "inference_applied": False,
            "input_tokens": None,
            "output_tokens": None,
            "cost_usd": None,
            "child_outcome": "timed_out" if timed_out else "failed",
        }
        if timed_out or return_code != 0:
            return observation
        result_raw, _ = _stable_read_regular(
            result_path,
            label="child_result",
            expected_uid=self.bootstrap.service_uid,
            expected_mode=0o600,
            maximum_bytes=64 * 1024,
        )
        child_result = _strict_json_bytes(result_raw, "child_result")
        if set(child_result) != {
            "contract_version",
            "outcome",
            "inference_applied",
            "input_tokens",
            "output_tokens",
            "cost_usd",
        } or child_result.get("contract_version") != "0.1":
            raise TrustedRunnerViolation("child_result_contract_invalid")
        if child_result.get("outcome") not in {"completed", "stopped_fail_closed"}:
            raise TrustedRunnerViolation("child_result_outcome_invalid")
        inference_applied = child_result.get("inference_applied")
        input_tokens = child_result.get("input_tokens")
        output_tokens = child_result.get("output_tokens")
        if not isinstance(inference_applied, bool):
            raise TrustedRunnerViolation("child_result_usage_invalid")
        for value in (input_tokens, output_tokens):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise TrustedRunnerViolation("child_result_usage_invalid")
        try:
            cost = None if child_result.get("cost_usd") is None else Decimal(
                str(child_result["cost_usd"])
            )
        except (InvalidOperation, ValueError) as exc:
            raise TrustedRunnerViolation("child_result_usage_invalid") from exc
        if (
            cost is not None
            and (not cost.is_finite() or cost < 0 or cost > _MAX_COST_USD)
        ) or (output_tokens is not None and output_tokens > _MAX_OUTPUT_TOKENS):
            raise TrustedRunnerViolation("child_result_budget_exceeded")
        if self.bootstrap.mode == "rehearsal" and inference_applied:
            raise TrustedRunnerViolation("rehearsal_inference_denied")
        observation.update(
            {
                "child_outcome": child_result["outcome"],
                "inference_applied": inference_applied,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": None if cost is None else format(cost, "f"),
            }
        )
        return observation

    def _sign_result(self, result: Mapping[str, Any]) -> dict[str, Any]:
        raw, _ = _stable_read_regular(
            self.bootstrap.result_private_key,
            label="result_private_key",
            expected_uid=self.bootstrap.service_uid,
            expected_mode=0o600,
            maximum_bytes=32,
        )
        if len(raw) != 32:
            raise TrustedRunnerViolation("result_private_key_invalid")
        try:
            private_key = Ed25519PrivateKey.from_private_bytes(raw)
            observed_public = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            expected_public = base64.b64decode(
                self.bootstrap.result_public_key, validate=True
            )
        except (ValueError, binascii.Error) as exc:
            raise TrustedRunnerViolation("result_signing_key_invalid") from exc
        if observed_public != expected_public:
            raise TrustedRunnerViolation("result_signing_key_mismatch")
        signature = private_key.sign(_canonical_bytes(result))
        return {
            "schema_version": "0.1",
            "algorithm": "ed25519",
            "result": dict(result),
            "signature": base64.b64encode(signature).decode("ascii"),
        }

    def execute(
        self,
        request: Mapping[str, Any],
        bundle_fd: int,
        *,
        peer_uid: int,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "contract_version": "0.1",
            "runner_id": self.bootstrap.runner_id,
            "operation_id": None,
            "plan_hash": None,
            "outcome": "stopped_fail_closed",
            "reason": "request_not_validated",
            "approval_consumed": False,
            "credential_material_opened": False,
            "runtime_started": False,
            "inference_applied": False,
            "timed_out": False,
            "return_code": None,
            "input_tokens": None,
            "output_tokens": None,
            "cost_usd": None,
            "stdout_hash": None,
            "stderr_hash": None,
            "duration_ms": 0,
            "credential_material_zeroized": True,
            "isolation_root_removed": True,
            "descriptors_closed": True,
            "promotion_applied": False,
            "gate_enforce_applied": False,
            "deployment_applied": False,
        }
        secret: bytearray | None = None
        isolation_root: Path | None = None
        try:
            if peer_uid not in self.bootstrap.allowed_client_uids:
                raise TrustedRunnerViolation("runner_peer_uid_denied")
            if self.bootstrap.mode == "production" and peer_uid == self.bootstrap.service_uid:
                raise TrustedRunnerViolation("production_uid_separation_required")
            validated = self._validate_request(request)
            result["operation_id"] = validated.operation_id
            result["plan_hash"] = validated.plan_hash
            self._verify_bundle(bundle_fd, validated.operation)
            self._consume_approval(validated)
            result["approval_consumed"] = True
            self._verify_bundle(bundle_fd, validated.operation)
            self._verify_runtime()
            secret = self._open_credential()
            result["credential_material_opened"] = True
            isolation_root = Path(
                tempfile.mkdtemp(
                    prefix="sddgov-trusted-runner-",
                    dir=self.bootstrap.isolation_parent,
                )
            )
            isolation_root.chmod(0o700)
            observation = self._run_child(
                validated,
                bundle_fd,
                secret,
                isolation_root,
            )
            result.update(observation)
            if observation["timed_out"]:
                result["reason"] = "child_timeout"
            elif observation["return_code"] != 0:
                result["reason"] = "child_failed"
            elif observation["child_outcome"] != "completed":
                result["reason"] = "child_stopped_fail_closed"
            else:
                result["outcome"] = "completed"
                result["reason"] = "exact_operation_completed"
        except TrustedRunnerViolation as exc:
            result["reason"] = exc.reason
        except Exception as exc:  # noqa: BLE001 - never expose private diagnostics
            result["reason"] = f"unexpected_error:{type(exc).__name__}"
        finally:
            if secret is not None:
                secret[:] = b"\x00" * len(secret)
                result["credential_material_zeroized"] = all(value == 0 for value in secret)
            if isolation_root is not None:
                try:
                    shutil.rmtree(isolation_root)
                except OSError:
                    result["isolation_root_removed"] = False
                else:
                    result["isolation_root_removed"] = not isolation_root.exists()
            if not result["credential_material_zeroized"] or not result["isolation_root_removed"]:
                result["outcome"] = "stopped_fail_closed"
                result["reason"] = "rollback_incomplete"
        return self._sign_result(result)


def describe_bootstrap(path: str | Path) -> dict[str, str]:
    return TrustedRunnerBootstrap.load(path).descriptor()


def _receive_one(connection: socket.socket) -> tuple[dict[str, Any], int, int]:
    if connection.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_SEQPACKET:
        raise TrustedRunnerViolation("runner_socket_type_invalid")
    if not hasattr(socket, "SO_PEERCRED"):
        raise TrustedRunnerViolation("runner_peer_credentials_unsupported")
    credentials = connection.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        struct.calcsize("3i"),
    )
    _, peer_uid, _ = struct.unpack("3i", credentials)
    message, ancillary, flags, _ = connection.recvmsg(
        _MAX_REQUEST_BYTES + 1,
        socket.CMSG_SPACE(array.array("i", [0]).itemsize * 2),
    )
    if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or len(message) > _MAX_REQUEST_BYTES:
        raise TrustedRunnerViolation("runner_request_too_large")
    descriptors: list[int] = []
    for level, kind, raw in ancillary:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            values = array.array("i")
            values.frombytes(raw[: len(raw) - (len(raw) % values.itemsize)])
            descriptors.extend(values.tolist())
    if len(descriptors) != 1:
        for descriptor in descriptors:
            os.close(descriptor)
        raise TrustedRunnerViolation("runner_bundle_fd_count_invalid")
    return _strict_json_bytes(message, "runner_request"), descriptors[0], peer_uid


def serve_connected_socket(
    bootstrap_path: str | Path, connection: socket.socket
) -> int:
    """Serve one already-connected SOCK_SEQPACKET without taking socket ownership."""

    runner = TrustedRunner.from_path(bootstrap_path)
    bundle_fd: int | None = None
    try:
        request, bundle_fd, peer_uid = _receive_one(connection)
        envelope = runner.execute(request, bundle_fd, peer_uid=peer_uid)
        encoded = _canonical_bytes(envelope)
        if len(encoded) > _MAX_REQUEST_BYTES:
            raise TrustedRunnerViolation("runner_result_too_large")
        connection.sendall(encoded)
        return 0 if envelope["result"]["outcome"] == "completed" else 2
    finally:
        if bundle_fd is not None:
            os.close(bundle_fd)


def serve_connection(bootstrap_path: str | Path, connection_fd: int) -> int:
    """Serve exactly one systemd-activated SOCK_SEQPACKET connection."""

    connection = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
        fileno=os.dup(connection_fd),
    )
    try:
        return serve_connected_socket(bootstrap_path, connection)
    finally:
        connection.close()
