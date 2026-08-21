import base64
import json
import math
import os
import signal
import socket
import stat
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
    _handle_connection,
    _receive_request,
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
    def __init__(self, parent: Path, *, guard_state: bool = True):
        self.parent = parent
        self.guard_state = guard_state
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
        if len(self.chunks) == 1:
            return self.chunks[0]
        return self.chunks.pop(0)

    def sendall(self, response):
        self.response = response


class BrokerTests(unittest.TestCase):
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

    def test_receive_request_returns_at_newline_without_waiting_for_eof(self):
        class OpenConnection:
            def settimeout(self, _timeout):
                return None

            def recv(self, _size):
                if hasattr(self, "read"):
                    raise AssertionError("reader waited for EOF after the terminator")
                self.read = True
                return b'{"action":"health"}\n'

        self.assertEqual(
            _receive_request(OpenConnection()),
            b'{"action":"health"}\n',
        )

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
            with patch.dict(
                os.environ,
                {"SDDGOV_TRUSTED_APPROVERS_FILE": str(outside)},
            ), patch(
                "sddgov.broker.load_control_plane_json", return_value=valid
            ):
                result = _approver_store(root)
            self.assertEqual(result["active"], 1)

            with patch.dict(
                os.environ,
                {"SDDGOV_TRUSTED_APPROVERS_FILE": str(outside)},
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
            with patch.dict(
                os.environ,
                {"SDDGOV_TRUSTED_APPROVERS_FILE": str(inside)},
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
                with self.subTest(value=value), patch.dict(
                    os.environ,
                    {"SDDGOV_TRUSTED_APPROVERS_FILE": str(outside)},
                ), patch(
                    "sddgov.broker.load_control_plane_json", return_value=value
                ):
                    with self.assertRaisesRegex(ValueError, "invalid|no active"):
                        _approver_store(root)

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
        with patch("sddgov.broker.print") as output:
            _handle_connection(connection, ledger)

        self.assertEqual(connection.response, b"REJECTED\n")
        rendered = str(output.call_args)
        self.assertIn("broker request must be exactly one newline-terminated record", rendered)
        self.assertNotIn("b'{", rendered)

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
                return_value=SimpleNamespace(gr_gid=os.getgid()),
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

    def test_partial_connection_deadline_allows_next_valid_request(self):
        class QueueServer:
            def __init__(self, socket_path, connections):
                self.socket_path = socket_path
                self.connections = list(connections)

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
                if self.connections:
                    return self.connections.pop(0), None
                signal.raise_signal(signal.SIGTERM)
                raise socket.timeout()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = _FakeBrokerSocketPath(root, guard_state=False)
            partial = _FakeConnection([b"{"])
            valid = _FakeConnection([b'{"action":"health"}\n', b""])
            fake_ledger = Mock()
            server = QueueServer(socket_path, [partial, valid])
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
                "sddgov.broker.socket.socket", return_value=server
            ), patch(
                "sddgov.broker.L3_NONCE_BROKER", socket_path
            ), patch(
                "sddgov.broker.BROKER_STATE_FILE", root / "consumed-nonces.jsonl"
            ), patch(
                "sddgov.broker.time.monotonic",
                side_effect=_advancing_clock(),
            ):
                serve_broker("sddgov")
            self.assertEqual(partial.response, b"REJECTED\n")
            self.assertEqual(valid.response, b"READY\n")
            fake_ledger.validate.assert_called_once_with()
            self.assertFalse(socket_path.exists())

    def test_transient_accept_error_does_not_kill_the_daemon(self):
        class QueueServer:
            def __init__(self, socket_path, connection):
                self.socket_path = socket_path
                self.connection = connection
                self.calls = 0

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
                signal.raise_signal(signal.SIGTERM)
                raise socket.timeout()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = _FakeBrokerSocketPath(root, guard_state=False)
            valid = _FakeConnection([b'{"action":"health"}\n', b""])
            fake_ledger = Mock()
            server = QueueServer(socket_path, valid)
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
                "sddgov.broker.socket.socket", return_value=server
            ), patch(
                "sddgov.broker.L3_NONCE_BROKER", socket_path
            ), patch(
                "sddgov.broker.BROKER_STATE_FILE", root / "consumed-nonces.jsonl"
            ), patch("sddgov.broker.time.sleep") as sleep, patch(
                "sddgov.broker.print"
            ) as output:
                serve_broker("sddgov")

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
            with patch("sddgov.broker.os.geteuid", return_value=0), patch(
                "sddgov.broker._root_owned_directory_errors", return_value=[]
            ), patch(
                "sddgov.broker.grp.getgrnam",
                return_value=SimpleNamespace(gr_gid=os.getgid()),
            ), patch("sddgov.broker.os.chown"), patch(
                "sddgov.broker.os.chmod"
            ), patch(
                "sddgov.broker.NonceLedger", return_value=Mock()
            ), patch(
                "sddgov.broker.socket.socket", return_value=server
            ), patch(
                "sddgov.broker.L3_NONCE_BROKER", socket_path
            ), patch(
                "sddgov.broker.BROKER_STATE_FILE", root / "consumed-nonces.jsonl"
            ), patch(
                "sddgov.broker.time.sleep",
                side_effect=[None] * 5 + [AssertionError("accept loop did not stop")],
            ), self.assertRaisesRegex(OSError, "repeated accept failures"):
                serve_broker("sddgov")
            self.assertFalse(socket_path.exists())


if __name__ == "__main__":
    unittest.main()
