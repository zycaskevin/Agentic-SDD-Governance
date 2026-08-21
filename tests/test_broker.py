import json
import os
import signal
import socket
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sddgov.broker import (
    NonceLedger,
    _receive_request,
    broker_readiness,
    handle_request,
    serve_broker,
)


class BrokerTests(unittest.TestCase):
    def test_receive_request_enforces_one_monotonic_deadline(self):
        class TricklingConnection:
            def __init__(self):
                self.timeouts = []

            def settimeout(self, timeout):
                self.timeouts.append(timeout)

            def recv(self, _size):
                return b"{"

        connection = TricklingConnection()
        with patch(
            "sddgov.broker.time.monotonic",
            side_effect=(100.0, 100.0, 100.75, 101.5, 102.01),
        ):
            with self.assertRaisesRegex(ValueError, "read deadline"):
                _receive_request(connection)
        self.assertEqual(len(connection.timeouts), 3)
        self.assertGreater(connection.timeouts[0], connection.timeouts[-1])

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
                b'{}\n',
                b'{"action":"health"}\nextra\n',
                json.dumps(
                    {
                        "action": "consume",
                        "nonce": "short",
                        "receipt_sha256": "a" * 64,
                        "operation_payload_sha256": "b" * 64,
                    }
                ).encode() + b"\n",
            )
            for value in cases:
                with self.subTest(value=value):
                    if value.count(b"\n") == 1:
                        self.assertEqual(handle_request(value, ledger), b"REJECTED\n")
                    else:
                        with self.assertRaises(ValueError):
                            handle_request(value, ledger)
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

    def test_service_signals_remove_only_the_bound_socket_and_allow_restart(self):
        class BrokerSocketPath:
            def __init__(self, parent):
                self.parent = parent
                self.bound = False
                self.inode = 0

            def __str__(self):
                return str(self.parent / "approval-broker.sock")

            def exists(self):
                return self.bound

            def is_symlink(self):
                return False

            def bind(self):
                if self.bound:
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
                )

            def unlink(self):
                if not self.bound:
                    raise FileNotFoundError(str(self))
                self.bound = False

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
            socket_path = BrokerSocketPath(root)
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
        class BrokerSocketPath:
            def __init__(self, parent):
                self.parent = parent
                self.bound = False
                self.inode = 0

            def __str__(self):
                return str(self.parent / "approval-broker.sock")

            def exists(self):
                return self.bound

            def is_symlink(self):
                return False

            def bind(self):
                self.bound = True
                self.inode += 1

            def lstat(self):
                if not self.bound:
                    raise FileNotFoundError(str(self))
                return SimpleNamespace(
                    st_mode=stat.S_IFSOCK | 0o660,
                    st_dev=1,
                    st_ino=self.inode,
                )

            def unlink(self):
                self.bound = False

        class Connection:
            def __init__(self, chunks):
                self.chunks = list(chunks)
                self.response = b""

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return None

            def settimeout(self, _timeout):
                return None

            def recv(self, _size):
                if len(self.chunks) == 1:
                    return self.chunks[0]
                return self.chunks.pop(0)

            def sendall(self, response):
                self.response = response

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
            socket_path = BrokerSocketPath(root)
            partial = Connection([b"{"])
            valid = Connection([b'{"action":"health"}\n', b""])
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
                side_effect=(100.0, 100.0, 100.75, 101.5, 102.01, 200.0, 200.0, 200.1),
            ):
                serve_broker("sddgov")
            self.assertEqual(partial.response, b"REJECTED\n")
            self.assertEqual(valid.response, b"READY\n")
            fake_ledger.validate.assert_called_once_with()
            self.assertFalse(socket_path.exists())


if __name__ == "__main__":
    unittest.main()
