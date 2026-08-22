import base64
import json
import math
import os
import signal
import socket
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import UnsupportedAlgorithm

import sddgov.broker as broker_module

from sddgov.broker import (
    MAX_REQUEST_BYTES,
    NonceLedger,
    REQUEST_READ_DEADLINE_SECONDS,
    RESPONSE_SEND_DEADLINE_SECONDS,
    _approver_store,
    _configure_socket_access,
    _exclusive_rename_at,
    _handle_connection,
    _receive_request,
    _serve_requests,
    _warn_ledger_capacity,
    broker_readiness,
    handle_request,
    serve_broker,
)


def _advancing_clock(start=100.0, step=0.5):
    current = start - step

    def tick():
        nonlocal current
        current += step
        return current

    return tick


class _FakeBrokerSocketPath:
    def __init__(
        self,
        parent: Path,
        *,
        guard_state: bool = True,
        fail_first_bound_lstat: bool = False,
        replace_on_first_bound_lstat: bool = False,
    ):
        self.parent = parent
        self.guard_state = guard_state
        self.fail_first_bound_lstat = fail_first_bound_lstat
        self.replace_on_first_bound_lstat = replace_on_first_bound_lstat
        self.bound = False
        self.inode = 0

    def __str__(self):
        return str(self.parent / "approval-broker.sock")

    def exists(self):
        return self.bound

    def is_symlink(self):
        return False

    def bind(self):
        if self.guard_state and self.bound:
            raise OSError("socket path already bound")
        self.bound = True
        self.inode += 1

    def lstat(self):
        if not self.bound:
            raise FileNotFoundError(str(self))
        if self.fail_first_bound_lstat:
            self.fail_first_bound_lstat = False
            if self.replace_on_first_bound_lstat:
                self.inode += 1
            raise OSError("synthetic post-bind lstat failure")
        return SimpleNamespace(
            st_mode=stat.S_IFSOCK | 0o660,
            st_dev=1,
            st_ino=self.inode,
            st_uid=0,
            st_gid=os.getgid(),
        )

    def unlink(self):
        if self.guard_state and not self.bound:
            raise FileNotFoundError(str(self))
        self.bound = False


class _FakeConnection:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.response = b""
        self.timeouts = []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return None

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recv(self, _size):
        return self.chunks.pop(0) if self.chunks else b""

    def sendall(self, response):
        self.response = response


@unittest.skipUnless(
    os.name == "posix" and broker_module.fcntl is not None,
    "L3 Broker tests require Linux or macOS POSIX primitives",
)
class BrokerTests(unittest.TestCase):
    def test_darwin_exclusive_publish_uses_documented_rename_flag(self):
        operation = Mock(return_value=0)
        library = SimpleNamespace(renameatx_np=operation)
        with patch("sddgov.broker.sys.platform", "darwin"), patch(
            "sddgov.broker.ctypes.CDLL", return_value=library
        ):
            _exclusive_rename_at(10, "staged.sock", 11, "final.sock")
        self.assertEqual(operation.call_args.args[-1], 0x00000004)

    def test_ledger_scan_uses_a_bounded_record_read(self):
        class Reader:
            def __init__(self):
                self.sizes = []

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return None

            def __iter__(self):
                raise AssertionError("unbounded iterator read")

            def readline(self, size):
                self.sizes.append(size)
                return b""

        reader = Reader()
        with tempfile.TemporaryFile() as ledger_file, patch(
            "sddgov.broker.os.fdopen", return_value=reader
        ):
            self.assertEqual(NonceLedger._scan_locked(ledger_file.fileno()), set())
        self.assertEqual(reader.sizes, [broker_module.MAX_LEDGER_RECORD_BYTES + 1])

    def test_ledger_rejects_an_active_epoch_over_the_capacity_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "consumed.jsonl"
            ledger_path.write_bytes(b"x" * 9)
            os.chmod(ledger_path, 0o600)
            ledger = NonceLedger(
                ledger_path,
                expected_uid=os.geteuid(),
                validate_parent_chain=False,
            )
            with patch("sddgov.broker.MAX_LEDGER_BYTES", 8), self.assertRaisesRegex(
                ValueError, "capacity limit"
            ):
                ledger.validate()

    def test_ledger_rejects_an_active_epoch_at_the_capacity_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "consumed.jsonl"
            ledger_path.write_bytes(b"x" * 8)
            os.chmod(ledger_path, 0o600)
            ledger = NonceLedger(
                ledger_path,
                expected_uid=os.geteuid(),
                validate_parent_chain=False,
            )
            with patch("sddgov.broker.MAX_LEDGER_BYTES", 8), self.assertRaisesRegex(
                ValueError, "capacity limit"
            ):
                ledger.validate()

    def test_ledger_rejects_an_append_that_crosses_the_capacity_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "consumed.jsonl"
            ledger = NonceLedger(
                ledger_path,
                expected_uid=os.geteuid(),
                validate_parent_chain=False,
            )
            ledger.initialize()
            with patch("sddgov.broker.MAX_LEDGER_BYTES", 1), self.assertRaisesRegex(
                ValueError, "capacity limit"
            ):
                ledger.consume("synthetic-nonce-0001", "a" * 64, "b" * 64)
            self.assertEqual(ledger_path.read_bytes(), b"")

    def test_ledger_rejects_near_capacity_before_allocating_nonce_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "consumed.jsonl"
            ledger_path.write_bytes(b"x")
            os.chmod(ledger_path, 0o600)
            ledger = NonceLedger(
                ledger_path,
                expected_uid=os.geteuid(),
                validate_parent_chain=False,
            )
            with patch("sddgov.broker.MAX_LEDGER_BYTES", 2), patch.object(
                ledger, "_scan_locked", side_effect=AssertionError("unbounded scan")
            ) as scan, self.assertRaisesRegex(ValueError, "capacity limit"):
                ledger.consume("synthetic-nonce-0001", "a" * 64, "b" * 64)
            scan.assert_not_called()

    def test_receive_request_enforces_one_monotonic_deadline(self):
        class TricklingConnection:
            def __init__(self):
                self.timeouts = []

            def settimeout(self, timeout):
                self.timeouts.append(timeout)

            def recv(self, _size):
                return b"{"

        connection = TricklingConnection()
        step = 0.5
        with patch(
            "sddgov.broker.time.monotonic",
            side_effect=_advancing_clock(step=step),
        ):
            with self.assertRaisesRegex(ValueError, "read deadline"):
                _receive_request(connection)
        expected = math.ceil(REQUEST_READ_DEADLINE_SECONDS / step) - 1
        self.assertEqual(len(connection.timeouts), expected)
        self.assertGreater(connection.timeouts[0], connection.timeouts[-1])

    def test_receive_request_requires_eof_after_the_single_record(self):
        class ClosedWriteConnection:
            def settimeout(self, _timeout):
                return None

            def recv(self, _size):
                if not hasattr(self, "read"):
                    self.read = True
                    return b'{"action":"health"}\n'
                return b""

        self.assertEqual(
            _receive_request(ClosedWriteConnection()),
            b'{"action":"health"}\n',
        )

    def test_receive_request_rejects_delayed_extra_record(self):
        connection = _FakeConnection(
            [b'{"action":"health"}\n', b'{"action":"health"}\n', b""]
        )
        with self.assertRaisesRegex(ValueError, "exactly one"):
            _receive_request(connection)

    def test_delayed_extra_record_is_rejected_before_health_or_consume(self):
        ledger = Mock()
        connection = _FakeConnection(
            [b'{"action":"health"}\n', b'{"action":"health"}\n', b""]
        )
        _handle_connection(connection, ledger)
        self.assertEqual(connection.response, b"REJECTED\n")
        ledger.validate.assert_not_called()
        ledger.consume.assert_not_called()

    def test_receive_request_rejects_a_record_over_the_size_limit(self):
        class OversizedConnection:
            def settimeout(self, _timeout):
                return None

            def recv(self, size):
                return b"x" * size

        with self.assertRaisesRegex(ValueError, "exceeds the size limit"):
            _receive_request(OversizedConnection())

    def test_request_size_limit_is_pinned(self):
        self.assertEqual(MAX_REQUEST_BYTES, 2048)
        self.assertEqual(broker_module.MAX_LEDGER_BYTES, 64 * 1024 * 1024)

    def test_startup_capacity_warning_precedes_the_hard_limit(self):
        with patch("sddgov.broker.MAX_LEDGER_BYTES", 100), patch(
            "sddgov.broker._broker_log"
        ) as output:
            _warn_ledger_capacity(79)
            output.assert_not_called()
            _warn_ledger_capacity(80)
        self.assertIn("80/100 bytes used", str(output.call_args))

    def test_nonce_ledger_fails_cleanly_without_posix_locking(self):
        with patch("sddgov.broker.fcntl", None):
            with self.assertRaisesRegex(ValueError, "requires Linux or macOS"):
                NonceLedger(Path("unused"), validate_parent_chain=False).initialize()

    def test_health_is_read_only_and_nonce_is_consumed_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "consumed.jsonl"
            ledger = NonceLedger(
                ledger_path,
                expected_uid=os.geteuid(),
                validate_parent_chain=False,
            )
            with self.assertRaises(FileNotFoundError):
                handle_request(b'{"action":"health"}\n', ledger)
            self.assertFalse(ledger_path.exists())
            ledger.initialize()
            self.assertEqual(handle_request(b'{"action":"health"}\n', ledger), b"READY\n")

            request = json.dumps(
                {
                    "action": "consume",
                    "nonce": "synthetic-nonce-0001",
                    "receipt_sha256": "a" * 64,
                    "operation_payload_sha256": "b" * 64,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode() + b"\n"
            self.assertEqual(handle_request(request, ledger), b"CONSUMED\n")
            self.assertEqual(handle_request(request, ledger), b"ALREADY_CONSUMED\n")
            rows = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["nonce"], "synthetic-nonce-0001")

    def test_ledger_initialization_creates_and_validation_checks_the_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "consumed.jsonl"
            ledger = NonceLedger(
                ledger_path,
                expected_uid=os.geteuid(),
                validate_parent_chain=False,
            )
            ledger.initialize()
            self.assertEqual(ledger_path.read_bytes(), b"")
            self.assertEqual(ledger_path.stat().st_mode & 0o077, 0)

            ledger_path.write_bytes(b'{"truncated":true}')
            with self.assertRaisesRegex(ValueError, "invalid record"):
                ledger.validate()

    def test_malformed_requests_fail_closed_without_ledger_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "consumed.jsonl"
            ledger = NonceLedger(
                ledger_path,
                expected_uid=os.geteuid(),
                validate_parent_chain=False,
            )
            cases = (
                (b'{}\n', b"REJECTED\n"),
                (b'{"action":"health"}\nextra\n', None),
                (
                    json.dumps(
                        {
                            "action": "consume",
                            "nonce": "short",
                            "receipt_sha256": "a" * 64,
                            "operation_payload_sha256": "b" * 64,
                        }
                    ).encode()
                    + b"\n",
                    b"REJECTED\n",
                ),
            )
            for value, expected in cases:
                with self.subTest(value=value):
                    if expected is None:
                        with self.assertRaises(ValueError):
                            handle_request(value, ledger)
                    else:
                        self.assertEqual(handle_request(value, ledger), expected)
            self.assertFalse(ledger_path.exists())

    def test_corrupt_or_duplicate_ledger_records_fail_closed(self):
        valid = {
            "nonce": "synthetic-nonce-0001",
            "receipt_sha256": "a" * 64,
            "operation_payload_sha256": "b" * 64,
            "consumed_at": "2026-08-21T00:00:00Z",
        }
        corruptions = (
            b'{"nonce":"truncated"}',
            json.dumps({**valid, "unexpected": True}).encode() + b"\n",
            (json.dumps(valid) + "\n" + json.dumps(valid) + "\n").encode(),
        )
        for corruption in corruptions:
            with self.subTest(corruption=corruption):
                with tempfile.TemporaryDirectory() as temporary:
                    ledger_path = Path(temporary) / "consumed.jsonl"
                    ledger_path.write_bytes(corruption)
                    os.chmod(ledger_path, 0o600)
                    ledger = NonceLedger(
                        ledger_path,
                        expected_uid=os.geteuid(),
                        validate_parent_chain=False,
                    )
                    with self.assertRaisesRegex(ValueError, "invalid record"):
                        ledger.consume("synthetic-nonce-0002", "c" * 64, "d" * 64)
                    self.assertEqual(ledger_path.read_bytes(), corruption)

    def test_readiness_reports_all_required_controls(self):
        with patch("sddgov.broker.os.geteuid", return_value=1000), patch(
            "sddgov.broker._runtime_context",
            return_value={
                "repository": "example/repository",
                "project": "example",
                "environment": "synthetic",
            },
        ), patch(
            "sddgov.broker._approver_store",
            return_value={"path": "/etc/sddgov/trusted-approvers.json", "active": 1},
        ), patch("sddgov.broker._socket_errors", return_value=[]), patch(
            "sddgov.broker._broker_health"
        ):
            report = broker_readiness(Path.cwd())
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["state"], "READY")
        self.assertEqual(
            [row["name"] for row in report["checks"]],
            [
                "supported_platform",
                "agent_identity_separation",
                "runtime_context",
                "trusted_approver_store",
                "broker_socket",
            ],
        )

    def test_readiness_aggregates_not_ready_check_details(self):
        with patch("sddgov.broker.os.geteuid", return_value=1000), patch(
            "sddgov.broker._runtime_context",
            return_value={
                "repository": "example/repository",
                "project": "example",
                "environment": "synthetic",
            },
        ), patch(
            "sddgov.broker._approver_store",
            side_effect=ValueError("trusted approver store is unavailable"),
        ), patch("sddgov.broker._socket_errors", return_value=[]), patch(
            "sddgov.broker._broker_health"
        ):
            report = broker_readiness(Path.cwd())
        self.assertFalse(report["ok"])
        self.assertEqual(report["state"], "NOT_READY")
        self.assertIn("trusted approver store is unavailable", report["errors"])
        failed = [row for row in report["checks"] if not row["ok"]]
        self.assertEqual([row["name"] for row in failed], ["trusted_approver_store"])
        self.assertIn("L3_BROKER_OPERATIONS.md", report["next_action"])

    def test_real_approver_store_contract_and_repository_boundary(self):
        private_key = Ed25519PrivateKey.generate()
        public_key = base64.b64encode(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode("ascii")
        valid = {
            "schema_version": "1.0",
            "approvers": [
                {
                    "approver_id": "synthetic-production-2026q3",
                    "algorithm": "ed25519",
                    "public_key": public_key,
                    "status": "active",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()
            outside = Path(temporary) / "trusted-approvers.json"
            with patch(
                "sddgov.trust.TRUSTED_APPROVERS_FILE", outside
            ), patch(
                "sddgov.broker.load_control_plane_json", return_value=valid
            ):
                result = _approver_store(root)
            self.assertEqual(result["active"], 1)

            with patch(
                "sddgov.trust.TRUSTED_APPROVERS_FILE", outside
            ), patch(
                "sddgov.broker.load_control_plane_json", return_value=valid
            ), patch(
                "sddgov.broker.Ed25519PublicKey.from_public_bytes",
                side_effect=UnsupportedAlgorithm("synthetic unavailable backend"),
            ):
                with self.assertRaisesRegex(ValueError, "invalid Ed25519 key"):
                    _approver_store(root)

            inside = root / "trusted-approvers.json"
            loader = Mock(return_value=valid)
            with patch(
                "sddgov.trust.TRUSTED_APPROVERS_FILE", inside
            ), patch("sddgov.broker.load_control_plane_json", loader):
                with self.assertRaisesRegex(ValueError, "outside the repository"):
                    _approver_store(root)
            loader.assert_not_called()

            invalid_records = (
                {**valid, "schema_version": "2.0"},
                {
                    **valid,
                    "approvers": [
                        {**valid["approvers"][0], "algorithm": "rsa"}
                    ],
                },
                {
                    **valid,
                    "approvers": valid["approvers"] * 2,
                },
                {
                    **valid,
                    "approvers": [
                        {**valid["approvers"][0], "public_key": "not-base64"}
                    ],
                },
                {
                    **valid,
                    "approvers": [
                        {**valid["approvers"][0], "status": "revoked"}
                    ],
                },
            )
            for value in invalid_records:
                with self.subTest(value=value), patch(
                    "sddgov.trust.TRUSTED_APPROVERS_FILE", outside
                ), patch(
                    "sddgov.broker.load_control_plane_json", return_value=value
                ):
                    with self.assertRaisesRegex(ValueError, "invalid|no active"):
                        _approver_store(root)

    def test_caller_cannot_substitute_the_fixed_approver_store(self):
        root = Path.cwd()
        with patch.dict(
            os.environ,
            {"SDDGOV_TRUSTED_APPROVERS_FILE": "attacker-selected-trust.json"},
        ), self.assertRaisesRegex(ValueError, "caller override"):
            _approver_store(root)

    def test_readiness_reports_caller_selected_approver_store_not_ready(self):
        with patch.dict(
            os.environ,
            {"SDDGOV_TRUSTED_APPROVERS_FILE": "attacker-selected-trust.json"},
        ), patch("sddgov.broker.os.geteuid", return_value=1000), patch(
            "sddgov.broker._runtime_context",
            return_value={
                "repository": "example/repository",
                "project": "example",
                "environment": "synthetic",
            },
        ), patch("sddgov.broker._socket_errors", return_value=[]), patch(
            "sddgov.broker._broker_health"
        ):
            report = broker_readiness(Path.cwd())
        self.assertFalse(report["ok"])
        self.assertEqual(report["state"], "NOT_READY")
        self.assertIn("caller override", "\n".join(report["errors"]))

    def test_connection_reply_uses_a_fresh_send_deadline(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = NonceLedger(
                Path(temporary) / "consumed.jsonl",
                expected_uid=os.geteuid(),
                validate_parent_chain=False,
            )
            ledger.initialize()
            connection = _FakeConnection([b'{"action":"health"}\n'])
            _handle_connection(connection, ledger)

        self.assertEqual(connection.response, b"READY\n")
        self.assertEqual(connection.timeouts[-1], RESPONSE_SEND_DEADLINE_SECONDS)

    def test_rejected_connection_logs_only_the_safe_error(self):
        ledger = Mock()
        connection = _FakeConnection([b"{", b""])
        with patch("sddgov.broker._broker_log") as output:
            _handle_connection(connection, ledger)

        self.assertEqual(connection.response, b"REJECTED\n")
        rendered = str(output.call_args)
        self.assertIn("broker request must be exactly one newline-terminated record", rendered)
        self.assertNotIn("b'{", rendered)

    def test_request_material_never_reaches_operational_logs(self):
        nonce = "sensitive-nonce-value"
        digest = "a" * 64
        connection = _FakeConnection(
            [
                (
                    '{"action":"consume","nonce":"'
                    + nonce
                    + '","receipt_sha256":"'
                    + digest
                    + '"}\nextra\n'
                ).encode("utf-8"),
                b"",
            ]
        )
        with patch("sddgov.broker._broker_log") as output:
            _handle_connection(connection, Mock())

        rendered = str(output.call_args)
        self.assertNotIn(nonce, rendered)
        self.assertNotIn(digest, rendered)
        self.assertIn("exactly one newline-terminated record", rendered)

    def test_success_and_duplicate_consumption_emit_no_request_log(self):
        request = (
            b'{"action":"consume","nonce":"nonce-1234567890",'
            + b'"receipt_sha256":"'
            + b"a" * 64
            + b'","operation_payload_sha256":"'
            + b"b" * 64
            + b'"}\n'
        )
        for consumed, expected in ((True, b"CONSUMED\n"), (False, b"ALREADY_CONSUMED\n")):
            with self.subTest(consumed=consumed):
                ledger = Mock()
                ledger.consume.return_value = consumed
                connection = _FakeConnection([request, b""])
                with patch("sddgov.broker._broker_log") as output:
                    _handle_connection(connection, ledger)
                self.assertEqual(connection.response, expected)
                output.assert_not_called()

    def test_darwin_operational_log_uses_the_unified_logger(self):
        system_log = SimpleNamespace(
            LOG_PID=1,
            LOG_DAEMON=2,
            LOG_WARNING=3,
            openlog=Mock(),
            syslog=Mock(),
        )
        with patch.object(broker_module.sys, "platform", "darwin"), patch.dict(
            sys.modules, {"syslog": system_log}
        ):
            broker_module._broker_log("synthetic operational warning")

        system_log.openlog.assert_called_once_with("sddgov-broker", 1, 2)
        system_log.syslog.assert_called_once_with(3, "synthetic operational warning")

    def test_socket_access_uses_real_path_chmod(self):
        with tempfile.TemporaryDirectory() as temporary:
            socket_path = Path(temporary) / "approval-broker.sock"
            socket_path.write_bytes(b"synthetic socket pathname")
            original = socket_path.stat()
            identity = (original.st_dev, original.st_ino)

            def socket_metadata():
                metadata = socket_path.stat()
                return SimpleNamespace(
                    st_mode=stat.S_IFSOCK | stat.S_IMODE(metadata.st_mode),
                    st_dev=metadata.st_dev,
                    st_ino=metadata.st_ino,
                    st_uid=metadata.st_uid,
                    st_gid=metadata.st_gid,
                )

            with patch.object(Path, "lstat", side_effect=socket_metadata), patch(
                "sddgov.broker.os.chown"
            ):
                _configure_socket_access(
                    socket_path,
                    os.getgid(),
                    identity,
                    owner_uid=os.geteuid(),
                )
            self.assertEqual(socket_path.stat().st_mode & 0o777, 0o660)

    def test_socket_access_skips_chown_when_bind_already_has_exact_ownership(self):
        metadata = SimpleNamespace(
            st_mode=stat.S_IFSOCK | 0o660,
            st_dev=1,
            st_ino=2,
            st_uid=0,
            st_gid=123,
        )
        socket_path = Mock()
        socket_path.lstat.return_value = metadata
        with patch(
            "sddgov.broker.os.chown",
            side_effect=PermissionError("CAP_CHOWN is absent"),
        ) as chown, patch("sddgov.broker.os.chmod"):
            _configure_socket_access(socket_path, 123, (1, 2))
        chown.assert_not_called()

    def test_socket_readiness_requires_exact_mode_and_platform_group(self):
        group_name = "_sddgov" if broker_module.sys.platform == "darwin" else "sddgov"
        self.assertEqual(broker_module.BROKER_SOCKET_GROUP, group_name)
        valid = SimpleNamespace(
            st_mode=stat.S_IFSOCK | 0o660,
            st_uid=0,
            st_gid=123,
        )
        with patch(
            "sddgov.broker._root_owned_directory_errors", return_value=[]
        ), patch.object(
            Path, "lstat", return_value=valid
        ), patch(
            "sddgov.broker.grp.getgrnam",
            return_value=SimpleNamespace(gr_gid=123),
        ):
            self.assertEqual(broker_module._socket_errors(), [])

        wrong_mode = SimpleNamespace(**{**vars(valid), "st_mode": stat.S_IFSOCK | 0o640})
        wrong_group = SimpleNamespace(**{**vars(valid), "st_gid": 456})
        for metadata, expected in (
            (wrong_mode, "exactly 0660"),
            (wrong_group, "dedicated group"),
        ):
            with self.subTest(expected=expected), patch(
                "sddgov.broker._root_owned_directory_errors", return_value=[]
            ), patch.object(
                Path, "lstat", return_value=metadata
            ), patch(
                "sddgov.broker.grp.getgrnam",
                return_value=SimpleNamespace(gr_gid=123),
            ):
                self.assertIn(expected, "; ".join(broker_module._socket_errors()))

    def test_service_rejects_a_nonplatform_socket_group_before_filesystem_access(self):
        with patch("sddgov.broker.os.geteuid", return_value=0), patch(
            "sddgov.broker._root_owned_directory_errors"
        ) as filesystem_check, self.assertRaisesRegex(
            ValueError, f"must be {broker_module.BROKER_SOCKET_GROUP}"
        ):
            serve_broker("synthetic-wrong-group")
        filesystem_check.assert_not_called()

    @unittest.skip("superseded by native staging-publication failure coverage")
    def test_post_bind_identity_failure_removes_the_created_socket(self):
        class BindOnlyServer:
            def __init__(self, socket_path):
                self.socket_path = socket_path

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return None

            def bind(self, _path):
                self.socket_path.bind()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = _FakeBrokerSocketPath(
                root, fail_first_bound_lstat=True
            )
            with patch("sddgov.broker.os.geteuid", return_value=0), patch(
                "sddgov.broker._root_owned_directory_errors", return_value=[]
            ), patch(
                "sddgov.broker.grp.getgrnam",
                return_value=SimpleNamespace(gr_gid=os.getgid()),
            ), patch(
                "sddgov.broker.NonceLedger", return_value=Mock()
            ), patch(
                "sddgov.broker.socket.socket",
                return_value=BindOnlyServer(socket_path),
            ), patch(
                "sddgov.broker.L3_NONCE_BROKER", socket_path
            ), patch(
                "sddgov.broker.BROKER_STATE_FILE", root / "consumed-nonces.jsonl"
            ), self.assertRaisesRegex(OSError, "post-bind lstat failure"):
                serve_broker("sddgov")

            self.assertFalse(socket_path.exists())

    @unittest.skip("superseded by native replacement-preservation coverage")
    def test_post_bind_failure_preserves_a_replacement_socket(self):
        class BindOnlyServer:
            def __init__(self, socket_path):
                self.socket_path = socket_path

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return None

            def bind(self, _path):
                self.socket_path.bind()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = _FakeBrokerSocketPath(
                root,
                fail_first_bound_lstat=True,
                replace_on_first_bound_lstat=True,
            )
            with patch("sddgov.broker.os.geteuid", return_value=0), patch(
                "sddgov.broker._root_owned_directory_errors", return_value=[]
            ), patch(
                "sddgov.broker.grp.getgrnam",
                return_value=SimpleNamespace(gr_gid=os.getgid()),
            ), patch(
                "sddgov.broker.NonceLedger", return_value=Mock()
            ), patch(
                "sddgov.broker.socket.socket",
                return_value=BindOnlyServer(socket_path),
            ), patch(
                "sddgov.broker.L3_NONCE_BROKER", socket_path
            ), patch(
                "sddgov.broker.BROKER_STATE_FILE", root / "consumed-nonces.jsonl"
            ), self.assertRaisesRegex(OSError, "post-bind lstat failure"):
                serve_broker("sddgov")

            self.assertTrue(socket_path.exists())

    @unittest.skip("superseded by native subprocess signal/restart coverage")
    def test_service_signals_remove_only_the_bound_socket_and_allow_restart(self):
        class SignalServer:
            def __init__(self, signum, socket_path):
                self.signum = signum
                self.socket_path = socket_path

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return None

            def bind(self, _path):
                self.socket_path.bind()

            def listen(self, _backlog):
                return None

            def settimeout(self, _timeout):
                return None

            def accept(self):
                signal.raise_signal(self.signum)
                raise socket.timeout()

        original_handlers = {
            signum: signal.getsignal(signum)
            for signum in (signal.SIGTERM, signal.SIGINT)
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = _FakeBrokerSocketPath(root)
            state_path = root / "consumed-nonces.jsonl"

            failing_ledger = Mock()
            with patch("sddgov.broker.os.geteuid", return_value=0), patch(
                "sddgov.broker._root_owned_directory_errors", return_value=[]
            ), patch(
                "sddgov.broker.grp.getgrnam",
                return_value=SimpleNamespace(gr_gid=os.getgid() + 1),
            ), patch(
                "sddgov.broker.os.chown",
                side_effect=OSError("synthetic chown failure"),
            ), patch("sddgov.broker.NonceLedger", return_value=failing_ledger), patch(
                "sddgov.broker.socket.socket",
                return_value=SignalServer(signal.SIGTERM, socket_path),
            ), patch("sddgov.broker.L3_NONCE_BROKER", socket_path), patch(
                "sddgov.broker.BROKER_STATE_FILE", state_path
            ):
                with self.assertRaisesRegex(OSError, "synthetic chown failure"):
                    serve_broker("sddgov")
            self.assertFalse(socket_path.exists())

            for signum in (signal.SIGTERM, signal.SIGINT):
                fake_ledger = Mock()
                with patch("sddgov.broker.os.geteuid", return_value=0), patch(
                    "sddgov.broker._root_owned_directory_errors", return_value=[]
                ), patch(
                    "sddgov.broker.grp.getgrnam",
                    return_value=SimpleNamespace(gr_gid=os.getgid()),
                ), patch("sddgov.broker.os.chown"), patch(
                    "sddgov.broker.os.chmod"
                ), patch(
                    "sddgov.broker.NonceLedger", return_value=fake_ledger
                ), patch(
                    "sddgov.broker.socket.socket",
                    side_effect=lambda *_args, signum=signum, **_kwargs: SignalServer(
                        signum, socket_path
                    ),
                ), patch(
                    "sddgov.broker.L3_NONCE_BROKER", socket_path
                ), patch(
                    "sddgov.broker.BROKER_STATE_FILE", state_path
                ):
                    serve_broker("sddgov")
                fake_ledger.initialize.assert_called_once_with()
                self.assertFalse(socket_path.exists())

        for signum, original_handler in original_handlers.items():
            self.assertIs(signal.getsignal(signum), original_handler)

    def test_partial_signal_setup_restores_every_installed_handler(self):
        ledger = Mock()
        original_term_handler = object()
        calls = []

        def install_or_fail(signum, handler):
            calls.append((signum, handler))
            if len(calls) == 1:
                return original_term_handler
            if len(calls) == 2:
                raise OSError("synthetic SIGINT installation failure")
            return object()

        with (
            patch("sddgov.broker.signal.signal", side_effect=install_or_fail),
            self.assertRaisesRegex(OSError, "SIGINT installation failure"),
        ):
            broker_module._serve_broker_at(
                Path("/synthetic/approval-broker.sock"),
                ledger,
                123,
                owner_uid=0,
            )

        ledger.initialize.assert_called_once_with()
        self.assertEqual(calls[0][0], signal.SIGTERM)
        self.assertEqual(calls[1][0], signal.SIGINT)
        self.assertEqual(calls[2], (signal.SIGTERM, original_term_handler))

    def test_partial_connection_deadline_allows_next_valid_request(self):
        class QueueServer:
            def __init__(self, connections):
                self.connections = list(connections)
                self.stopped = False

            def listen(self, _backlog):
                return None

            def settimeout(self, _timeout):
                return None

            def accept(self):
                if self.connections:
                    return self.connections.pop(0), None
                self.stopped = True
                raise socket.timeout()

        partial = _FakeConnection([b"{"])
        valid = _FakeConnection([b'{"action":"health"}\n', b""])
        fake_ledger = Mock()
        server = QueueServer([partial, valid])
        with patch(
            "sddgov.broker.time.monotonic",
            side_effect=_advancing_clock(),
        ):
            _serve_requests(server, fake_ledger, lambda: server.stopped)
        self.assertEqual(partial.response, b"REJECTED\n")
        self.assertEqual(valid.response, b"READY\n")
        fake_ledger.validate.assert_called_once_with()

    def test_transient_accept_error_does_not_kill_the_daemon(self):
        class QueueServer:
            def __init__(self, socket_path, connection):
                self.socket_path = socket_path
                self.connection = connection
                self.calls = 0
                self.stopped = False

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return None

            def bind(self, _path):
                self.socket_path.bind()

            def listen(self, _backlog):
                return None

            def settimeout(self, _timeout):
                return None

            def accept(self):
                self.calls += 1
                if self.calls == 1:
                    raise OSError("synthetic transient accept failure")
                if self.calls == 2:
                    return self.connection, None
                self.stopped = True
                raise socket.timeout()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = _FakeBrokerSocketPath(root, guard_state=False)
            valid = _FakeConnection([b'{"action":"health"}\n', b""])
            fake_ledger = Mock()
            server = QueueServer(socket_path, valid)
            with patch("sddgov.broker.time.sleep") as sleep, patch(
                "sddgov.broker._broker_log"
            ) as output:
                _serve_requests(server, fake_ledger, lambda: server.stopped)

            self.assertEqual(valid.response, b"READY\n")
            self.assertGreaterEqual(server.calls, 3)
            sleep.assert_called_once()
            self.assertTrue(
                any(
                    "transient accept failure" in str(call)
                    for call in output.call_args_list
                )
            )

    def test_repeated_accept_failures_terminate_the_daemon(self):
        class FailingServer:
            def __init__(self, socket_path):
                self.socket_path = socket_path

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return None

            def bind(self, _path):
                self.socket_path.bind()

            def listen(self, _backlog):
                return None

            def settimeout(self, _timeout):
                return None

            def accept(self):
                raise OSError("synthetic persistent accept failure")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = _FakeBrokerSocketPath(root, guard_state=False)
            server = FailingServer(socket_path)
            with patch(
                "sddgov.broker.time.sleep",
                side_effect=[None] * 5 + [AssertionError("accept loop did not stop")],
            ), self.assertRaisesRegex(OSError, "repeated accept failures"):
                _serve_requests(server, Mock(), lambda: False)


if __name__ == "__main__":
    unittest.main()
