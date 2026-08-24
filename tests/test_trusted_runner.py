from __future__ import annotations

import array
import base64
import ctypes
import fcntl
import hashlib
import json
import os
import shutil
import socket
import tempfile
import threading
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

import sddgov.trusted_runner as trusted_runner_module
import sddgov.autonomy as autonomy_module
from sddgov.cli import build_parser
from sddgov.schema_validation import load_schema, validate_instance
from sddgov.trust import load_control_plane_json as real_load_control_plane_json
from sddgov.trusted_runner import (
    TrustedRunner,
    TrustedRunnerBootstrap,
    TrustedRunnerViolation,
    _production_directory_chain,
    serve_connected_socket,
)

SYNTHETIC_KEY = b"sk-synthetic-af26-trusted-runner-000000000000"
MANAGED_PATHS = (
    "agent/relay_llm.py",
    "agent/auxiliary_client.py",
    "hermes_cli/auth.py",
    "gateway/platforms/api_server.py",
    "agent/transports/codex.py",
)
F_ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
F_SEAL_SEAL = getattr(fcntl, "F_SEAL_SEAL", 0x0001)
F_SEAL_SHRINK = getattr(fcntl, "F_SEAL_SHRINK", 0x0002)
F_SEAL_GROW = getattr(fcntl, "F_SEAL_GROW", 0x0004)
F_SEAL_WRITE = getattr(fcntl, "F_SEAL_WRITE", 0x0008)
REQUIRED_SEALS = F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL
MFD_CLOEXEC = getattr(os, "MFD_CLOEXEC", 0x0001)
MFD_ALLOW_SEALING = getattr(os, "MFD_ALLOW_SEALING", 0x0002)
ROOT = Path(__file__).resolve().parents[1]


def _memfd_create(name: str) -> int:
    if hasattr(os, "memfd_create"):
        return os.memfd_create(name, MFD_CLOEXEC | MFD_ALLOW_SEALING)
    libc = ctypes.CDLL(None, use_errno=True)
    create = libc.memfd_create
    create.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    create.restype = ctypes.c_int
    descriptor = create(name.encode("ascii"), MFD_CLOEXEC | MFD_ALLOW_SEALING)
    if descriptor < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return descriptor


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_hash(value) -> str:
    return _sha256(_canonical(value))


def _write_private(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)
    path.chmod(0o600)


def _hash_path(path: Path) -> str:
    return _sha256(path.read_bytes())


class TrustedRunnerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            prefix="sddgov-af26-runner-", dir="/tmp"
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.runtime_context_path = self.root / "runtime-context.json"
        _write_private(
            self.runtime_context_path,
            _canonical(
                {
                    "schema_version": "1.0",
                    "repository": "zycaskevin/Agent-Factory-core",
                    "project": "Agent Factory",
                    "environment": "synthetic-offline-rehearsal",
                }
            ),
        )
        self.runtime_context_patch = patch(
            "sddgov.autonomy.L3_RUNTIME_CONTEXT_FILE", self.runtime_context_path
        )
        self.runtime_context_patch.start()
        self.addCleanup(self.runtime_context_patch.stop)
        self.control_plane_loader_patch = patch(
            "sddgov.autonomy.load_control_plane_json",
            side_effect=lambda path, _label: json.loads(Path(path).read_text()),
        )
        self.control_plane_loader_patch.start()
        self.addCleanup(self.control_plane_loader_patch.stop)
        self.nonce_broker_patch = patch(
            "sddgov.autonomy._consume_nonce_via_control_plane", return_value=True
        )
        self.nonce_broker_patch.start()
        self.addCleanup(self.nonce_broker_patch.stop)
        self.state_root = self.root / "state"
        self.state_root.mkdir(mode=0o700)
        self.isolation_parent = self.root / "isolation"
        self.isolation_parent.mkdir(mode=0o700)
        self.owner_key = Ed25519PrivateKey.generate()
        owner_public = self.owner_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.trust_file = self.root / "trusted-approvers.json"
        _write_private(
            self.trust_file,
            json.dumps(
                {
                    "schema_version": "1.0",
                    "approvers": [
                        {
                            "approver_id": "synthetic-owner",
                            "algorithm": "ed25519",
                            "public_key": base64.b64encode(owner_public).decode("ascii"),
                            "status": "active",
                        }
                    ],
                }
            ).encode("utf-8"),
        )
        self.result_key = Ed25519PrivateKey.generate()
        result_private = self.result_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        result_public = self.result_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.result_private_path = self.root / "runner-result.key"
        _write_private(self.result_private_path, result_private)
        self.result_public = base64.b64encode(result_public).decode("ascii")
        self.credential_path = self.root / "synthetic-openai-key"
        _write_private(self.credential_path, SYNTHETIC_KEY)
        self.runtime = self.root / "af26-python"
        self.runtime.write_text("#!/bin/sh\nexec /usr/bin/python3 \"$@\"\n")
        self.runtime.chmod(0o700)
        child_program = """
import json
import os
import pathlib
assert os.environ["OPENAI_API_KEY"].startswith("sk-synthetic-af26-")
assert os.environ["AGENT_FACTORY_OFFLINE_ONLY"] == "1"
assert "AWS_SECRET_ACCESS_KEY" not in os.environ
assert pathlib.Path(os.environ["AGENT_FACTORY_INPUT_PATH"]).read_bytes()
result = dict(
    contract_version="0.1",
    outcome="completed",
    inference_applied=False,
    input_tokens=None,
    output_tokens=None,
    cost_usd=None,
)
target = pathlib.Path(os.environ["AGENT_FACTORY_RESULT_PATH"])
target.write_text(json.dumps(result))
target.chmod(0o600)
"""
        self.runtime_argv = ("-c", child_program)
        self.bootstrap_path = self._make_bootstrap()
        self.bootstrap = TrustedRunnerBootstrap.load(self.bootstrap_path)

    def _make_bootstrap(
        self,
        *,
        mode: str = "rehearsal",
        allowed_client_uids: list[int] | None = None,
        runtime: Path | None = None,
        runtime_argv: tuple[str, ...] | None = None,
        name: str = "runner-bootstrap.json",
    ) -> Path:
        selected_runtime = runtime or self.runtime
        selected_argv = runtime_argv or self.runtime_argv
        credential_hash = _sha256(SYNTHETIC_KEY)
        credential_binding = _canonical_hash(
            {
                "runner_id": "af26-synthetic-runner",
                "credential_ref": "secret-ref://af26/synthetic-openai-api",
                "credential_sha256": credential_hash,
            }
        )
        data = {
            "schema_version": "0.1",
            "runner_id": "af26-synthetic-runner",
            "mode": mode,
            "service_uid": os.geteuid(),
            "allowed_client_uids": allowed_client_uids or [os.geteuid()],
            "state_root": str(self.state_root),
            "trusted_approvers_file": str(self.trust_file),
            "result_private_key": str(self.result_private_path),
            "result_public_key": self.result_public,
            "runtime_executable": str(selected_runtime),
            "runtime_sha256": _hash_path(selected_runtime),
            "runtime_argv": list(selected_argv),
            "credential_ref": "secret-ref://af26/synthetic-openai-api",
            "credential_path": str(self.credential_path),
            "credential_sha256": credential_hash,
            "credential_binding_hash": credential_binding,
            "isolation_parent": str(self.isolation_parent),
        }
        path = self.root / name
        _write_private(path, json.dumps(data).encode("utf-8"))
        return path

    def _sealed_bundle(
        self,
        *,
        seal: bool = True,
        extra_name: str | None = None,
        corrupt_original: bool = False,
    ) -> tuple[int, dict[str, object]]:
        descriptor = _memfd_create("af26-test-bundle")
        managed: dict[str, str] = {}
        source_hashes: dict[str, str] = {}
        source_entries: list[dict[str, str]] = []
        source_raw = {
            "agent/__init__.py": b"",
            **{
                name: f"# synthetic managed module: {name}\n".encode()
                for name in MANAGED_PATHS
            },
        }
        with os.fdopen(os.dup(descriptor), "w+b", closefd=True) as target:
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
                for name in sorted(source_raw):
                    raw = source_raw[name]
                    archive.writestr(name, raw)
                    source_entries.append(
                        {
                            "path": name,
                            "kind": "file",
                            "mode": "100644",
                            "value_hash": _sha256(raw),
                        }
                    )
                    if name in MANAGED_PATHS:
                        original_raw = raw
                        if corrupt_original and name == MANAGED_PATHS[0]:
                            original_raw += b"corrupt-original"
                        archive.writestr(
                            ".agent-factory/original/" + name,
                            original_raw,
                        )
                        managed[name] = _sha256(raw)
                        source_hashes[name] = hashlib.sha256(raw).hexdigest()
                archive.writestr(
                    ".agent-factory/source-tree-manifest.json",
                    _canonical(source_entries),
                )
                if extra_name is not None:
                    archive.writestr(extra_name, b"attack")
            target.flush()
            os.fsync(target.fileno())
        if seal:
            fcntl.fcntl(descriptor, F_ADD_SEALS, REQUIRED_SEALS)
        info = os.fstat(descriptor)
        raw = os.pread(descriptor, info.st_size, 0)
        receipt: dict[str, object] = {
            "bundle_hash": _sha256(raw),
            "bundle_size_bytes": info.st_size,
            "entry_count": 12 + (1 if extra_name is not None else 0),
            "managed_hashes": managed,
            "source_hashes": source_hashes,
            "source_tree_hash": _canonical_hash(source_entries),
        }
        return descriptor, receipt

    def _approval(
        self,
        operation_id: str,
        nonce: str,
        operation_payload: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        approval_id = f"APP-AF26-{nonce}"
        receipt = {
            "approval_id": approval_id,
            "operation_id": operation_id,
            "operation_payload": operation_payload,
            "summary": "Synthetic AF26 exact operation",
            "scope": operation_id,
            "approved_by": "synthetic-owner",
            "issued_at": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "nonce": nonce,
        }
        envelope = {
            "schema_version": "1.0",
            "algorithm": "ed25519",
            "receipt": receipt,
            "signature": base64.b64encode(
                self.owner_key.sign(_canonical(receipt))
            ).decode("ascii"),
        }
        return approval_id, envelope

    def _request(
        self,
        bundle: dict[str, object],
        *,
        bootstrap: TrustedRunnerBootstrap | None = None,
        nonce: str = "nonce-af26-001",
        input_payload: bytes = b"synthetic AF26 input",
    ) -> dict[str, object]:
        selected = bootstrap or self.bootstrap
        bindings = selected.descriptor()
        containment_profile = dict(trusted_runner_module._EXPECTED_CONTAINMENT_PROFILE)
        containment_profile["source_hashes"] = dict(bundle["source_hashes"])
        containment_profile_hash = _canonical_hash(containment_profile)
        route_profile = dict(trusted_runner_module._EXPECTED_ROUTE_PROFILE)
        route_profile["containment_profile_hash"] = containment_profile_hash
        route_profile["source_tree_hash"] = bundle["source_tree_hash"]
        operation: dict[str, object] = {
            "contract_version": "0.3",
            "action_id": "AF25-HERMES-OPENAI-API-LIVE-UAT-L3-001",
            "credential_ref": selected.credential_ref,
            "input_payload_hash": _sha256(input_payload),
            "launch_contract_hash": bindings["launch_contract_hash"],
            "sealed_bundle_hash": bundle["bundle_hash"],
            "sealed_bundle_size_bytes": bundle["bundle_size_bytes"],
            "sealed_bundle_entry_count": bundle["entry_count"],
            "source_tree_hash": bundle["source_tree_hash"],
            "managed_hashes": bundle["managed_hashes"],
            "external_bindings": bindings,
            "route_profile_hash": _canonical_hash(route_profile),
            "containment_profile_hash": containment_profile_hash,
            "route_profile": route_profile,
            "containment_profile": containment_profile,
            "provider": "openai-api",
            "model": "gpt-5.6-sol",
            "endpoint": "https://api.openai.com/v1",
            "max_input_bytes": 4_096,
            "max_output_tokens": 1_000,
            "max_inference_calls": 1,
            "max_cost_usd": "0.25",
            "max_duration_seconds": 120,
            "gate_mode": "shadow",
            "rehearsal_only": selected.mode == "rehearsal",
            "tool_policy": "zero",
            "approval_subagents": "denied",
            "auxiliary_inference": "denied",
            "promotion": False,
            "gate_enforce": False,
            "deployment": False,
            "external_trusted_runner_required": True,
        }
        plan_hash = _canonical_hash(operation)
        operation_id = (
            "AF25-HERMES-OPENAI-API-LIVE-UAT-L3-001@"
            + plan_hash.removeprefix("sha256:")
        )
        operation["operation_id"] = operation_id
        operation_payload = trusted_runner_module._approval_operation_payload(
            operation, operation_id, plan_hash
        )
        approval_id, approval = self._approval(
            operation_id, nonce, operation_payload
        )
        capsule = {
            "contract_version": "0.3",
            "operation_id": operation_id,
            "plan_hash": plan_hash,
            "sealed_bundle_hash": operation["sealed_bundle_hash"],
            "external_bindings_hash": _canonical_hash(bindings),
            "environment_hash": _sha256(b"credential-free-environment"),
            "rehearsal_only": operation["rehearsal_only"],
            "credential_material_included": False,
            "authorization_consumed": False,
            "launch_permitted": False,
            "runtime_started": False,
            "inference_applied": False,
            "promotion_applied": False,
            "gate_enforce_applied": False,
            "deployment_applied": False,
        }
        return {
            "schema_version": "0.1",
            "operation": operation,
            "capsule": capsule,
            "sealed_bundle_delivery": "inherited-sealed-fd",
            "approval_required": True,
            "credential_delivery": "external-runner-private-fd",
            "approval_id": approval_id,
            "approval_envelope": approval,
            "input_payload_b64": base64.b64encode(input_payload).decode("ascii"),
        }

    def _verify_result_signature(self, envelope: dict[str, object]) -> dict[str, object]:
        self.assertEqual(set(envelope), {"schema_version", "algorithm", "result", "signature"})
        self.assertEqual(envelope["schema_version"], "0.1")
        self.assertEqual(envelope["algorithm"], "ed25519")
        result = envelope["result"]
        assert isinstance(result, dict)
        signature = base64.b64decode(envelope["signature"], validate=True)
        public = base64.b64decode(self.result_public, validate=True)
        Ed25519PublicKey.from_public_bytes(public).verify(signature, _canonical(result))
        return result

    def test_exact_rehearsal_consumes_approval_then_opens_secret_and_cleans_up(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle)
        events: list[str] = []

        class ObservedRunner(TrustedRunner):
            def _consume_approval(inner_self, validated) -> None:
                super()._consume_approval(validated)
                events.append("approval_consumed")

            def _open_credential(inner_self) -> bytearray:
                events.append("credential_opened")
                return super()._open_credential()

        real_popen = trusted_runner_module.subprocess.Popen

        def observed_popen(*args, **kwargs):
            child_argv = args[0]
            self.assertEqual(child_argv[1], "-I")
            launcher = Path(child_argv[2])
            self.assertTrue(launcher.is_absolute())
            self.assertEqual(launcher.name, "_trusted_exec.py")
            self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
            events.append("parent_env_secret_absent")
            return real_popen(*args, **kwargs)

        try:
            with (
                patch.dict(os.environ, {"AWS_SECRET_ACCESS_KEY": "must-not-pass"}),
                patch.object(
                    trusted_runner_module.subprocess,
                    "Popen",
                    side_effect=observed_popen,
                ),
            ):
                envelope = ObservedRunner(self.bootstrap).execute(
                    request, descriptor, peer_uid=os.geteuid()
                )
        finally:
            os.close(descriptor)
        result = self._verify_result_signature(envelope)

        self.assertEqual(
            events,
            [
                "approval_consumed",
                "credential_opened",
                "parent_env_secret_absent",
            ],
        )
        self.assertEqual(result["outcome"], "completed")
        self.assertEqual(result["reason"], "exact_operation_completed")
        self.assertTrue(result["approval_consumed"])
        self.assertTrue(result["credential_material_opened"])
        self.assertTrue(result["runtime_started"])
        self.assertFalse(result["inference_applied"])
        self.assertTrue(result["credential_material_zeroized"])
        self.assertTrue(result["isolation_root_removed"])
        self.assertFalse(any(self.isolation_parent.iterdir()))
        encoded = json.dumps(envelope, sort_keys=True)
        self.assertNotIn(SYNTHETIC_KEY.decode("ascii"), encoded)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", encoded)

    def test_rehearsal_has_no_control_plane_fallback(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, nonce="nonce-no-control-plane")
        try:
            with (
                patch.object(
                    autonomy_module,
                    "load_control_plane_json",
                    side_effect=real_load_control_plane_json,
                ),
                patch.object(
                    autonomy_module,
                    "_consume_nonce_via_control_plane",
                    return_value=False,
                ),
            ):
                result = self._verify_result_signature(
                    TrustedRunner(self.bootstrap).execute(
                        request, descriptor, peer_uid=os.geteuid()
                    )
                )
        finally:
            os.close(descriptor)
        self.assertEqual(result["reason"], "approval_verification_failed")
        self.assertFalse(result["approval_consumed"])
        self.assertFalse(result["credential_material_opened"])
        self.assertFalse(result["runtime_started"])

    def test_published_schemas_accept_exact_bootstrap_request_and_result(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, nonce="nonce-published-schema")
        bootstrap_schema = load_schema(
            ROOT / "schemas/trusted-runner-bootstrap.schema.json"
        )
        request_schema = load_schema(ROOT / "schemas/trusted-runner-request.schema.json")
        result_schema = load_schema(
            ROOT / "schemas/trusted-runner-result-envelope.schema.json"
        )
        self.assertEqual(
            validate_instance(json.loads(self.bootstrap_path.read_text()), bootstrap_schema),
            [],
        )
        self.assertEqual(validate_instance(request, request_schema), [])
        try:
            envelope = TrustedRunner(self.bootstrap).execute(
                request, descriptor, peer_uid=os.geteuid()
            )
        finally:
            os.close(descriptor)
        self.assertEqual(validate_instance(envelope, result_schema), [])

        extended = json.loads(json.dumps(envelope))
        extended["result"]["duration_ms"] = 124_000
        self.assertEqual(validate_instance(extended, result_schema), [])

    def test_unexpected_failure_emits_schema_safe_reason(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, nonce="nonce-unexpected-error")
        result_schema = load_schema(
            ROOT / "schemas/trusted-runner-result-envelope.schema.json"
        )
        try:
            with patch.object(
                TrustedRunner,
                "_verify_runtime",
                side_effect=RuntimeError("private diagnostic must not escape"),
            ):
                envelope = TrustedRunner(self.bootstrap).execute(
                    request, descriptor, peer_uid=os.geteuid()
                )
        finally:
            os.close(descriptor)
        result = self._verify_result_signature(envelope)
        self.assertEqual(result["reason"], "unexpected_error")
        self.assertEqual(validate_instance(envelope, result_schema), [])

    def test_child_setup_failures_close_every_owned_descriptor(self) -> None:
        real_open = os.open
        real_pipe2 = os.pipe2
        real_write = os.write

        for label in ("stderr-open", "pipe-write", "popen"):
            with self.subTest(label=label):
                descriptor, bundle = self._sealed_bundle()
                request = self._request(
                    bundle,
                    nonce=f"nonce-child-setup-{label}",
                )
                owned: dict[str, int] = {}

                def observed_open(path, *args, **kwargs):
                    name = Path(os.fsdecode(path)).name
                    if label == "stderr-open" and name == "stderr.bin":
                        raise OSError("synthetic stderr open failure")
                    opened = real_open(path, *args, **kwargs)
                    if name == "stdout.bin":
                        owned["stdout"] = opened
                    elif name == "stderr.bin":
                        owned["stderr"] = opened
                    return opened

                def observed_pipe2(flags):
                    read_fd, write_fd = real_pipe2(flags)
                    owned["secret_read"] = read_fd
                    owned["secret_write"] = write_fd
                    return read_fd, write_fd

                def observed_write(fd, value):
                    if label == "pipe-write" and fd == owned.get("secret_write"):
                        raise OSError("synthetic secret pipe write failure")
                    return real_write(fd, value)

                popen = (
                    patch.object(
                        trusted_runner_module.subprocess,
                        "Popen",
                        side_effect=OSError("synthetic child launch failure"),
                    )
                    if label == "popen"
                    else patch.object(
                        trusted_runner_module.subprocess,
                        "Popen",
                        wraps=trusted_runner_module.subprocess.Popen,
                    )
                )
                try:
                    with (
                        patch.object(trusted_runner_module.os, "open", side_effect=observed_open),
                        patch.object(trusted_runner_module.os, "pipe2", side_effect=observed_pipe2),
                        patch.object(trusted_runner_module.os, "write", side_effect=observed_write),
                        popen,
                    ):
                        result = self._verify_result_signature(
                            TrustedRunner(self.bootstrap).execute(
                                request, descriptor, peer_uid=os.geteuid()
                            )
                        )
                    for fd in owned.values():
                        with self.assertRaises(OSError):
                            os.fstat(fd)
                    self.assertTrue(result["descriptors_closed"])
                    self.assertEqual(result["reason"], "unexpected_error")
                finally:
                    os.close(descriptor)
                    for fd in owned.values():
                        try:
                            os.close(fd)
                        except OSError:
                            pass

    def test_setup_failure_runs_registered_cleanups(self) -> None:
        original_context = autonomy_module.L3_RUNTIME_CONTEXT_FILE
        original_loader = autonomy_module.load_control_plane_json
        original_broker = autonomy_module._consume_nonce_via_control_plane
        case = type(self)("test_exact_rehearsal_consumes_approval_then_opens_secret_and_cleans_up")
        try:
            with patch.object(
                type(self),
                "_make_bootstrap",
                side_effect=RuntimeError("synthetic setup failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic setup failure"):
                    case.setUp()
            temporary_root = case.root
            case.doCleanups()
            self.assertEqual(autonomy_module.L3_RUNTIME_CONTEXT_FILE, original_context)
            self.assertIs(autonomy_module.load_control_plane_json, original_loader)
            self.assertIs(autonomy_module._consume_nonce_via_control_plane, original_broker)
            self.assertFalse(temporary_root.exists())
        finally:
            for name in (
                "nonce_broker_patch",
                "control_plane_loader_patch",
                "runtime_context_patch",
            ):
                patcher = getattr(case, name, None)
                if patcher is not None:
                    patcher.stop()
            temporary = getattr(case, "temporary", None)
            if temporary is not None:
                temporary.cleanup()

    def test_descriptor_close_failure_is_reported_fail_closed(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, nonce="nonce-descriptor-close-failure")
        real_close = os.close
        real_pipe2 = os.pipe2
        owned: dict[str, int] = {}
        close_failed = False

        def observed_pipe2(flags):
            read_fd, write_fd = real_pipe2(flags)
            owned["secret_read"] = read_fd
            owned["secret_write"] = write_fd
            return read_fd, write_fd

        def observed_close(fd):
            nonlocal close_failed
            if fd == owned.get("secret_read") and not close_failed:
                close_failed = True
                raise OSError("synthetic descriptor close failure")
            return real_close(fd)

        try:
            with (
                patch.object(
                    trusted_runner_module.os,
                    "pipe2",
                    side_effect=observed_pipe2,
                ),
                patch.object(
                    trusted_runner_module.os,
                    "close",
                    side_effect=observed_close,
                ),
            ):
                result = self._verify_result_signature(
                    TrustedRunner(self.bootstrap).execute(
                        request, descriptor, peer_uid=os.geteuid()
                    )
                )
            self.assertEqual(result["reason"], "descriptor_cleanup_failed")
            self.assertFalse(result["descriptors_closed"])
            self.assertTrue(close_failed)
        finally:
            real_close(descriptor)
            read_fd = owned.get("secret_read", -1)
            if read_fd >= 0:
                try:
                    real_close(read_fd)
                except OSError:
                    pass

    def test_wrong_peer_and_unknown_request_field_stop_before_approval(self) -> None:
        for label, mutate, peer_uid, expected in (
            ("peer", lambda value: None, os.geteuid() + 10_000, "runner_peer_uid_denied"),
            (
                "unknown-field",
                lambda value: value.__setitem__("caller_env", {"OPENAI_API_KEY": "x"}),
                os.geteuid(),
                "runner_request_contract_invalid",
            ),
        ):
            with self.subTest(label=label):
                descriptor, bundle = self._sealed_bundle()
                request = self._request(bundle, nonce=f"nonce-{label}")
                mutate(request)
                try:
                    envelope = TrustedRunner(self.bootstrap).execute(
                        request, descriptor, peer_uid=peer_uid
                    )
                finally:
                    os.close(descriptor)
                result = self._verify_result_signature(envelope)
                self.assertEqual(result["reason"], expected)
                self.assertFalse(result["approval_consumed"])
                self.assertFalse(result["credential_material_opened"])
                self.assertFalse(result["runtime_started"])

    def test_binding_payload_and_capsule_drift_fail_closed(self) -> None:
        cases = ("binding", "payload", "capsule")
        for label in cases:
            with self.subTest(label=label):
                descriptor, bundle = self._sealed_bundle()
                request = self._request(bundle, nonce=f"nonce-{label}")
                if label == "binding":
                    request["operation"]["external_bindings"][
                        "credential_binding_hash"
                    ] = _sha256(b"forged-binding")
                elif label == "payload":
                    request["input_payload_b64"] = base64.b64encode(b"drift").decode()
                else:
                    request["capsule"]["launch_permitted"] = True
                try:
                    result = self._verify_result_signature(
                        TrustedRunner(self.bootstrap).execute(
                            request, descriptor, peer_uid=os.geteuid()
                        )
                    )
                finally:
                    os.close(descriptor)
                self.assertFalse(result["approval_consumed"])
                self.assertFalse(result["credential_material_opened"])
                self.assertFalse(result["runtime_started"])

    def test_profile_and_source_manifest_drift_fail_before_approval(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, nonce="nonce-profile-drift")
        request["operation"]["route_profile"]["endpoint"] = "https://example.invalid/v1"
        try:
            result = self._verify_result_signature(
                TrustedRunner(self.bootstrap).execute(
                    request, descriptor, peer_uid=os.geteuid()
                )
            )
        finally:
            os.close(descriptor)
        self.assertEqual(result["reason"], "route_profile_binding_mismatch")
        self.assertFalse(result["approval_consumed"])
        self.assertFalse(result["credential_material_opened"])

        descriptor, bundle = self._sealed_bundle(corrupt_original=True)
        request = self._request(bundle, nonce="nonce-source-content-drift")
        try:
            result = self._verify_result_signature(
                TrustedRunner(self.bootstrap).execute(
                    request, descriptor, peer_uid=os.geteuid()
                )
            )
        finally:
            os.close(descriptor)
        self.assertEqual(result["reason"], "source_tree_content_mismatch")
        self.assertFalse(result["approval_consumed"])
        self.assertFalse(result["credential_material_opened"])

    def test_approval_consumer_uses_service_private_authority_snapshot(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, nonce="nonce-authority-snapshot")
        real_import = trusted_runner_module.import_operation_approval
        snapshots: list[Path] = []

        def observed_import(root: Path, approval_path: Path):
            authority = Path(os.environ["SDDGOV_TRUSTED_APPROVERS_FILE"])
            self.assertNotEqual(authority, self.trust_file)
            self.assertEqual(authority.read_bytes(), self.trust_file.read_bytes())
            self.assertEqual(authority.stat().st_mode & 0o777, 0o600)
            snapshots.append(authority)
            return real_import(root, approval_path)

        try:
            with patch.object(
                trusted_runner_module,
                "import_operation_approval",
                side_effect=observed_import,
            ):
                result = self._verify_result_signature(
                    TrustedRunner(self.bootstrap).execute(
                        request, descriptor, peer_uid=os.geteuid()
                    )
                )
        finally:
            os.close(descriptor)
        self.assertEqual(result["outcome"], "completed")
        self.assertEqual(len(snapshots), 1)
        self.assertFalse(snapshots[0].exists())

    def test_unsealed_and_traversal_bundles_are_denied_before_approval(self) -> None:
        for label, seal, extra, expected in (
            ("unsealed", False, None, "sealed_bundle_seals_missing"),
            ("traversal", True, "../escape.py", "sealed_bundle_path_invalid"),
        ):
            with self.subTest(label=label):
                descriptor, bundle = self._sealed_bundle(seal=seal, extra_name=extra)
                request = self._request(bundle, nonce=f"nonce-{label}")
                try:
                    result = self._verify_result_signature(
                        TrustedRunner(self.bootstrap).execute(
                            request, descriptor, peer_uid=os.geteuid()
                        )
                    )
                finally:
                    os.close(descriptor)
                self.assertEqual(result["reason"], expected)
                self.assertFalse(result["approval_consumed"])
                self.assertFalse(result["credential_material_opened"])

    def test_approval_replay_and_concurrent_second_consumer_are_denied(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, nonce="nonce-replay")
        runner = TrustedRunner(self.bootstrap)
        try:
            first = self._verify_result_signature(
                runner.execute(request, descriptor, peer_uid=os.geteuid())
            )
            second = self._verify_result_signature(
                runner.execute(request, descriptor, peer_uid=os.geteuid())
            )
        finally:
            os.close(descriptor)
        self.assertEqual(first["outcome"], "completed")
        self.assertEqual(second["reason"], "approval_verification_failed")
        self.assertFalse(second["credential_material_opened"])

        other_root = self.root / "concurrent-state"
        other_root.mkdir(mode=0o700)
        bootstrap_data = json.loads(self.bootstrap_path.read_text())
        bootstrap_data["state_root"] = str(other_root)
        concurrent_path = self.root / "concurrent-bootstrap.json"
        _write_private(concurrent_path, json.dumps(bootstrap_data).encode())
        concurrent = TrustedRunnerBootstrap.load(concurrent_path)
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, bootstrap=concurrent, nonce="nonce-concurrent")
        outcomes: list[dict[str, object]] = []
        barrier = threading.Barrier(2)

        def execute() -> None:
            barrier.wait()
            envelope = TrustedRunner(concurrent).execute(
                request, descriptor, peer_uid=os.geteuid()
            )
            outcomes.append(self._verify_result_signature(envelope))

        threads = [threading.Thread(target=execute) for _ in range(2)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
        finally:
            os.close(descriptor)
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(
            sum(item["outcome"] == "completed" for item in outcomes), 1, outcomes
        )
        self.assertEqual(sum(item["credential_material_opened"] is True for item in outcomes), 1)

    def test_runtime_and_credential_drift_are_detected_after_approval_before_child(self) -> None:
        for label in ("runtime", "credential"):
            with self.subTest(label=label):
                state = self.root / f"state-{label}"
                state.mkdir(mode=0o700)
                copied_runtime = self.root / f"python-{label}"
                shutil.copy2(self.runtime, copied_runtime)
                copied_runtime.chmod(0o700)
                bootstrap_path = self._make_bootstrap(
                    runtime=copied_runtime,
                    name=f"bootstrap-{label}.json",
                )
                data = json.loads(bootstrap_path.read_text())
                data["state_root"] = str(state)
                _write_private(bootstrap_path, json.dumps(data).encode())
                bootstrap = TrustedRunnerBootstrap.load(bootstrap_path)
                descriptor, bundle = self._sealed_bundle()
                request = self._request(bundle, bootstrap=bootstrap, nonce=f"nonce-drift-{label}")
                if label == "runtime":
                    copied_runtime.write_bytes(b"drifted runtime")
                    copied_runtime.chmod(0o700)
                    expected = "runtime_executable_hash_mismatch"
                else:
                    self.credential_path.write_bytes(b"sk-drifted-credential-000000000000")
                    self.credential_path.chmod(0o600)
                    expected = "credential_source_hash_mismatch"
                try:
                    result = self._verify_result_signature(
                        TrustedRunner(bootstrap).execute(
                            request, descriptor, peer_uid=os.geteuid()
                        )
                    )
                finally:
                    os.close(descriptor)
                    if label == "credential":
                        _write_private(self.credential_path, SYNTHETIC_KEY)
                self.assertTrue(result["approval_consumed"])
                self.assertEqual(result["reason"], expected)
                self.assertFalse(result["runtime_started"])

    def test_timeout_terminates_child_and_removes_isolation(self) -> None:
        state = self.root / "timeout-state"
        state.mkdir(mode=0o700)
        runtime_argv = ("-c", "import time; time.sleep(30)")
        bootstrap_path = self._make_bootstrap(
            runtime_argv=runtime_argv,
            name="timeout-bootstrap.json",
        )
        data = json.loads(bootstrap_path.read_text())
        data["state_root"] = str(state)
        _write_private(bootstrap_path, json.dumps(data).encode())
        bootstrap = TrustedRunnerBootstrap.load(bootstrap_path)
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, bootstrap=bootstrap, nonce="nonce-timeout")
        try:
            with patch.object(
                trusted_runner_module, "_CHILD_WAIT_TIMEOUT_SECONDS", 0.05
            ):
                result = self._verify_result_signature(
                    TrustedRunner(bootstrap).execute(
                        request, descriptor, peer_uid=os.geteuid()
                    )
                )
        finally:
            os.close(descriptor)
        self.assertEqual(result["reason"], "child_timeout")
        self.assertTrue(result["timed_out"])
        self.assertTrue(result["runtime_started"])
        self.assertTrue(result["credential_material_zeroized"])
        self.assertTrue(result["isolation_root_removed"])
        self.assertFalse(any(self.isolation_parent.iterdir()))

    def test_bootstrap_requires_private_single_link_and_production_uid_separation(self) -> None:
        insecure = self.root / "insecure-bootstrap.json"
        shutil.copy2(self.bootstrap_path, insecure)
        insecure.chmod(0o644)
        symlink = self.root / "bootstrap-link.json"
        symlink.symlink_to(self.bootstrap_path)
        hardlink = self.root / "bootstrap-hardlink.json"
        os.link(self.bootstrap_path, hardlink)
        production = self.root / "production-bootstrap.json"
        data = json.loads(self.bootstrap_path.read_text())
        data["mode"] = "production"
        _write_private(production, json.dumps(data).encode())
        cases = (
            (insecure, "runner_bootstrap_permissions_invalid"),
            (symlink, "runner_bootstrap_not_private_regular"),
            (hardlink, "runner_bootstrap_not_private_regular"),
            (production, "production_cgroup_containment_required"),
        )
        for path, expected in cases:
            with self.subTest(path=path.name), self.assertRaisesRegex(
                TrustedRunnerViolation, expected
            ):
                TrustedRunnerBootstrap.load(path)
        with self.assertRaisesRegex(
            TrustedRunnerViolation, "production_test_ancestor_invalid"
        ):
            _production_directory_chain(self.root, "test", os.geteuid())

    def test_socket_activation_uses_kernel_peer_credentials_and_scm_rights(self) -> None:
        descriptor, bundle = self._sealed_bundle()
        request = self._request(bundle, nonce="nonce-socket")
        client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        outcome: dict[str, int] = {}

        def serve() -> None:
            outcome["code"] = serve_connected_socket(self.bootstrap_path, server)

        thread = threading.Thread(target=serve)
        thread.start()
        rights = array.array("i", [descriptor])
        try:
            client.sendmsg(
                [_canonical(request)],
                [(socket.SOL_SOCKET, socket.SCM_RIGHTS, rights)],
            )
            raw = client.recv(128 * 1024)
            thread.join(timeout=10)
        finally:
            os.close(descriptor)
            client.close()
            server.close()
        self.assertFalse(thread.is_alive())
        envelope = json.loads(raw)
        result = self._verify_result_signature(envelope)
        self.assertEqual(outcome["code"], 0)
        self.assertEqual(result["outcome"], "completed")

    def test_duplicate_json_and_cli_surface_are_fail_closed(self) -> None:
        with self.assertRaisesRegex(TrustedRunnerViolation, "json_duplicate_key_denied"):
            trusted_runner_module._strict_json_bytes(
                b'{"schema_version":"0.1","schema_version":"0.1"}',
                "runner_request",
            )
        parsed = build_parser().parse_args(
            [
                "trusted-runner",
                "serve-connection",
                "--bootstrap",
                str(self.bootstrap_path),
            ]
        )
        self.assertEqual(parsed.command, "trusted-runner")
        self.assertEqual(parsed.trusted_runner_command, "serve-connection")
        self.assertEqual(parsed.connection_fd, 3)


if __name__ == "__main__":
    unittest.main()
