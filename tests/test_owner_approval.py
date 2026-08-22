import base64
import copy
import json
import os
import struct
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import sddgov.fs_security as fs_security
from sddgov.autonomy import _read_repository_regular_file, _verify_product_envelope
from sddgov.governance import init_project
from sddgov.cli import build_parser as build_agent_parser, run as run_agent_cli
from sddgov.owner_cli import (
    _read_owner_choice,
    _require_owner_runtime,
    build_parser as build_owner_parser,
    run as run_owner_cli,
)
from sddgov.owner_approval import (
    SSH2_AGENTC_SIGN_REQUEST,
    SSH2_AGENT_SIGN_RESPONSE,
    SSH_AGENTC_REQUEST_IDENTITIES,
    SSH_AGENT_IDENTITIES_ANSWER,
    _ssh_string,
    _ssh_agent_exchange,
    _take_ssh_string,
    approve_product_decision,
    build_product_approval_card,
    _owner_client_identity,
    product_approval_card_sha256,
    render_product_approval_card,
)


class OwnerApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        init_project(self.root, "team-standard")
        work_packages = self.root / "work-packages"
        work_packages.mkdir()
        self.assumption = work_packages / "DEC-SYNTHETIC.md"
        owner_client = {
            "version": _owner_client_identity()["version"],
            "source_sha256": _owner_client_identity()["source_sha256"],
        }
        self.assumption.write_text(
            "# Exact bounded authority decision\n\n"
            "No Production operation is authorized.\n\n"
            "Owner client binding: "
            + json.dumps(
                owner_client,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        self.request = work_packages / "DEC-SYNTHETIC.request.json"
        scope = (
            "Use one fixed synthetic trust path; do not provision a key, write /etc, "
            "or execute a Production operation."
        )
        self.request.write_text(
            json.dumps(
                {
                    "risk_level": "L2",
                    "category": "product_decision",
                    "effects": {},
                    "decision_id": "DEC-SYNTHETIC",
                    "decision_scope": scope,
                    "assumption_paths": ["work-packages/DEC-SYNTHETIC.md"],
                    "approver_id": "synthetic-owner",
                    "valid_days": 30,
                    "owner_client": owner_client,
                    "decision_package": {
                        "risk_level": "L2",
                        "decision_id": "DEC-SYNTHETIC",
                        "why_human_input_is_required": (
                            "The choice changes one public authority boundary."
                        ),
                        "what_agent_already_verified": [
                            "The safe prototype and rollback boundary are Green."
                        ],
                        "options": [
                            {
                                "label": "A",
                                "description": "Approve the exact bounded authority contract.",
                            },
                            {
                                "label": "B",
                                "description": "Retain the trusted Base contract.",
                            },
                        ],
                        "recommended": "A",
                        "why": "A removes caller-selected authority routing.",
                        "impact_if_no_decision": "Only this Work Package stays blocked.",
                        "scope_of_approval": scope,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.trust = {
            "schema_version": "1.0",
            "approvers": [
                {
                    "approver_id": "synthetic-owner",
                    "algorithm": "ed25519",
                    "public_key": base64.b64encode(self.public_key).decode("ascii"),
                    "status": "active",
                }
            ],
        }
        self.domain = {
            "schema_version": "1.0",
            "bindings": [
                {
                    "approver_id": "synthetic-owner",
                    "repository_id": "github.com/example/synthetic",
                    "repository_root": str(self.root),
                    "trust_domain": "synthetic-test-domain",
                    "status": "active",
                }
            ],
        }
        self.trust_loader = patch(
            "sddgov.autonomy.load_control_plane_json",
            side_effect=lambda _path, label: (
                self.domain if "domain" in label else self.trust
            ),
        )
        self.trust_loader.start()
        self.addCleanup(self.trust_loader.stop)
        self.repository_identity = patch(
            "sddgov.autonomy._repository_identity",
            return_value="github.com/example/synthetic",
        )
        self.repository_identity.start()
        self.addCleanup(self.repository_identity.stop)

    def _card_sha256(self) -> str:
        _request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        return product_approval_card_sha256(card)

    def _agent_exchange(self, _socket_path, payload, _timeout):
        key_blob = _ssh_string(b"ssh-ed25519") + _ssh_string(self.public_key)
        if payload == bytes([SSH_AGENTC_REQUEST_IDENTITIES]):
            return (
                bytes([SSH_AGENT_IDENTITIES_ANSWER])
                + struct.pack(">I", 1)
                + _ssh_string(key_blob)
                + _ssh_string(b"confirmation-constrained synthetic key")
            )
        self.assertEqual(payload[0], SSH2_AGENTC_SIGN_REQUEST)
        received_blob, offset = _take_ssh_string(payload, 1)
        canonical, offset = _take_ssh_string(payload, offset)
        self.assertEqual(received_blob, key_blob)
        self.assertEqual(payload[offset:], struct.pack(">I", 0))
        signature_blob = _ssh_string(b"ssh-ed25519") + _ssh_string(
            self.private_key.sign(canonical)
        )
        return bytes([SSH2_AGENT_SIGN_RESPONSE]) + _ssh_string(signature_blob)

    def test_card_is_derived_from_one_validated_action_required_request(self):
        request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        self.assertEqual(request["decision_id"], "DEC-SYNTHETIC")
        self.assertEqual(card["heading"], "ACTION REQUIRED")
        self.assertEqual(card["recommended"], "A")
        self.assertEqual([row["label"] for row in card["options"]], ["A", "B"])
        self.assertEqual(card["assumption_paths"], ["work-packages/DEC-SYNTHETIC.md"])
        self.assertEqual(card["repository_id"], "github.com/example/synthetic")
        self.assertEqual(card["trust_domain"], "synthetic-test-domain")
        rendered = render_product_approval_card(card)
        self.assertIn("SDG OWNER DECISION", rendered)
        self.assertIn("[A] Approve the exact bounded authority contract.", rendered)
        self.assertNotIn("sha256", rendered.lower())

    def test_card_rejects_noncanonical_assumption_path_sets(self):
        original = json.loads(self.request.read_text(encoding="utf-8"))
        second = self.root / "work-packages" / "DEC-Z.md"
        second.write_text("# Second exact contract\n", encoding="utf-8")
        cases = (
            (None, "requires canonical assumption_paths"),
            (
                [
                    "work-packages/DEC-SYNTHETIC.md",
                    "work-packages/DEC-SYNTHETIC.md",
                ],
                "unique and canonically sorted",
            ),
            (
                ["work-packages/DEC-Z.md", "work-packages/DEC-SYNTHETIC.md"],
                "unique and canonically sorted",
            ),
            (["../DEC-SYNTHETIC.md"], "canonical repository-relative"),
        )
        for paths, message in cases:
            with self.subTest(paths=paths):
                request = copy.deepcopy(original)
                if paths is None:
                    request.pop("assumption_paths")
                else:
                    request["assumption_paths"] = paths
                self.request.write_text(json.dumps(request), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    build_product_approval_card(
                        self.root,
                        "work-packages/DEC-SYNTHETIC.request.json",
                    )
        self.request.write_text(json.dumps(original), encoding="utf-8")

    def test_card_requires_reviewed_client_identity_in_request_and_signed_assumption(self):
        original_request = json.loads(self.request.read_text(encoding="utf-8"))
        original_assumption = self.assumption.read_text(encoding="utf-8")

        mismatched = copy.deepcopy(original_request)
        mismatched["owner_client"]["source_sha256"] = "0" * 64
        self.request.write_text(json.dumps(mismatched), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match the governed reviewed"):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )

        self.request.write_text(json.dumps(original_request), encoding="utf-8")
        self.assumption.write_text(
            original_assumption.replace("Owner client binding: ", "Unbound client: "),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "assumptions must bind one exact"):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )

        self.assumption.write_text(original_assumption, encoding="utf-8")

    def test_card_requires_exact_unique_ordered_a_b_options(self):
        original = json.loads(self.request.read_text(encoding="utf-8"))
        for labels in (("A", "A"), ("B", "A"), ("A", "B", "C")):
            with self.subTest(labels=labels):
                request = copy.deepcopy(original)
                request["decision_package"]["options"] = [
                    {"label": label, "description": f"Option {label} meaning"}
                    for label in labels
                ]
                self.request.write_text(json.dumps(request), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "options|labels"):
                    build_product_approval_card(
                        self.root,
                        "work-packages/DEC-SYNTHETIC.request.json",
                    )
        self.request.write_text(json.dumps(original), encoding="utf-8")

    def test_card_rejects_terminal_control_and_invisible_text(self):
        original = json.loads(self.request.read_text(encoding="utf-8"))
        for hostile in ("escape\x1b[2J", "return\rspoof", "back\bspace", "bidi\u202eA"):
            with self.subTest(hostile=repr(hostile)):
                request = copy.deepcopy(original)
                request["decision_scope"] = hostile
                request["decision_package"]["scope_of_approval"] = hostile
                self.request.write_text(json.dumps(request), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "terminal control|invisible"):
                    build_product_approval_card(
                        self.root,
                        "work-packages/DEC-SYNTHETIC.request.json",
                    )
        self.request.write_text(json.dumps(original), encoding="utf-8")

    def test_card_and_assumptions_are_bounded_before_tty_or_signer(self):
        original = json.loads(self.request.read_text(encoding="utf-8"))
        oversized = copy.deepcopy(original)
        oversized["decision_scope"] = "x" * 9000
        oversized["decision_package"]["scope_of_approval"] = "x" * 9000
        self.request.write_text(json.dumps(oversized), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "bounded display size"):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )

        too_many = copy.deepcopy(original)
        paths = []
        for index in range(9):
            relative = f"work-packages/DEC-{index}.md"
            (self.root / relative).write_text(f"contract {index}\n", encoding="utf-8")
            paths.append(relative)
        too_many["assumption_paths"] = sorted(paths)
        self.request.write_text(json.dumps(too_many), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "too many decision assumption"):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )
        self.request.write_text(json.dumps(original), encoding="utf-8")

    def test_displayed_card_detects_request_or_assumption_changes_before_signing(self):
        displayed_digest = self._card_sha256()
        output = self.root / "must-not-sign.json"
        original = json.loads(self.request.read_text(encoding="utf-8"))
        changed = copy.deepcopy(original)
        changed["valid_days"] = 31
        self.request.write_text(json.dumps(changed), encoding="utf-8")
        with (
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            self.assertRaisesRegex(ValueError, "card changed after Owner display"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=displayed_digest,
            )
        exchange.assert_not_called()
        self.request.write_text(json.dumps(original), encoding="utf-8")

        displayed_digest = self._card_sha256()
        self.assumption.write_text(
            self.assumption.read_text(encoding="utf-8").replace(
                "No Production operation is authorized.",
                "The reviewed contract bytes changed before signing.",
            ),
            encoding="utf-8",
        )
        with (
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            self.assertRaisesRegex(ValueError, "card changed after Owner display"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=displayed_digest,
            )
        exchange.assert_not_called()
        self.assertFalse(output.exists())

    def test_displayed_card_detects_trusted_key_changes_before_signing(self):
        displayed_digest = self._card_sha256()
        replacement_key = Ed25519PrivateKey.generate().public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.trust["approvers"][0]["public_key"] = base64.b64encode(
            replacement_key
        ).decode("ascii")
        output = self.root / "must-not-sign-key-change.json"
        with (
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            self.assertRaisesRegex(ValueError, "card changed after Owner display"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=displayed_digest,
            )
        exchange.assert_not_called()
        self.assertFalse(output.exists())

    def test_recommended_choice_uses_agent_key_and_writes_verified_receipt(self):
        output = self.root / "out" / "signed-product-approval.json"
        with patch(
            "sddgov.owner_approval._ssh_agent_exchange",
            side_effect=self._agent_exchange,
        ):
            result = approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )

        self.assertEqual(result["state"], "APPROVED")
        self.assertEqual(result["selected_option"], "A")
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
        envelope = json.loads(output.read_text(encoding="utf-8"))
        receipt, digest = _verify_product_envelope(self.root, envelope)
        self.assertEqual(receipt["decision_id"], "DEC-SYNTHETIC")
        self.assertTrue(receipt["summary"].startswith("Approved option A:"))
        self.assertEqual(result["receipt_sha256"], digest)

    def test_non_recommended_choice_declines_without_contacting_signer(self):
        output = self.root / "declined.json"
        with patch("sddgov.owner_approval._ssh_agent_exchange") as exchange:
            result = approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "B",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        self.assertEqual(result["state"], "DECLINED")
        self.assertFalse(output.exists())
        exchange.assert_not_called()

    def test_request_symlink_is_rejected_before_rendering(self):
        linked = self.root / "work-packages" / "linked-request.json"
        linked.symlink_to(self.request.name)
        with self.assertRaisesRegex(ValueError, "cannot be opened safely"):
            build_product_approval_card(
                self.root,
                "work-packages/linked-request.json",
            )

    def test_repository_input_same_inode_mutation_fails_closed(self):
        from pathlib import PurePosixPath

        real_read = os.read
        changed = False

        def mutate_after_first_read(descriptor, size):
            nonlocal changed
            chunk = real_read(descriptor, size)
            if chunk and not changed:
                changed = True
                self.assumption.write_text("changed in place\n", encoding="utf-8")
            return chunk

        with (
            patch("sddgov.autonomy.os.read", side_effect=mutate_after_first_read),
            self.assertRaisesRegex(ValueError, "path changed"),
        ):
            _read_repository_regular_file(
                self.root,
                PurePosixPath("work-packages/DEC-SYNTHETIC.md"),
                max_bytes=1024,
            )
        self.assertTrue(changed)

    def test_agent_identity_response_must_match_exactly_once(self):
        output = self.root / "mismatch.json"
        response = (
            bytes([SSH_AGENT_IDENTITIES_ANSWER])
            + struct.pack(">I", 0)
        )
        with (
            patch(
                "sddgov.owner_approval._ssh_agent_exchange",
                return_value=response,
            ),
            self.assertRaisesRegex(ValueError, "not one unique active"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        self.assertFalse(output.exists())

    def test_ssh_agent_transport_reads_fragmented_bounded_frames(self):
        response = b"bounded-response"
        framed_response = bytearray(struct.pack(">I", len(response)) + response)

        class ConnectedSocket:
            def settimeout(self, timeout):
                self.timeout = timeout

            def connect(self, path):
                self.path = path

            def sendall(self, data):
                self.sent = data

            def recv(self, size):
                if not framed_response:
                    return b""
                count = min(size, 1)
                chunk = bytes(framed_response[:count])
                del framed_response[:count]
                return chunk

            def close(self):
                self.closed = True

        connection = ConnectedSocket()
        with patch(
            "sddgov.owner_approval.socket.socket",
            return_value=connection,
        ):
            actual = _ssh_agent_exchange(
                "/synthetic/agent.sock",
                b"bounded-request",
                1.0,
            )
        self.assertEqual(
            connection.sent,
            struct.pack(">I", len(b"bounded-request")) + b"bounded-request",
        )
        self.assertEqual(actual, b"bounded-response")
        self.assertTrue(connection.closed)

    def test_ssh_agent_transport_bounds_creation_primary_and_close_failures(self):
        with (
            patch(
                "sddgov.owner_approval.socket.socket",
                side_effect=OSError("synthetic socket creation failure"),
            ),
            self.assertRaisesRegex(ValueError, "confirmed SSH signer is unavailable"),
        ):
            _ssh_agent_exchange("/synthetic/agent.sock", b"request", 1.0)

        class FailingSocket:
            def settimeout(self, _timeout):
                pass

            def connect(self, _path):
                pass

            def sendall(self, _data):
                pass

            def recv(self, _size):
                raise OSError("synthetic receive failure")

            def close(self):
                raise OSError("synthetic close failure")

        with (
            patch("sddgov.owner_approval.socket.socket", return_value=FailingSocket()),
            self.assertRaisesRegex(ValueError, "confirmed SSH signer is unavailable"),
        ):
            _ssh_agent_exchange("/synthetic/agent.sock", b"request", 1.0)

        response = b"complete"
        framed = bytearray(struct.pack(">I", len(response)) + response)

        class CompleteThenCloseFails(FailingSocket):
            def recv(self, size):
                chunk = bytes(framed[:size])
                del framed[:size]
                return chunk

        with patch(
            "sddgov.owner_approval.socket.socket",
            return_value=CompleteThenCloseFails(),
        ):
            self.assertEqual(
                _ssh_agent_exchange("/synthetic/agent.sock", b"request", 1.0),
                response,
            )

    def test_signed_receipt_never_follows_an_output_symlink(self):
        victim = self.root / "victim.json"
        victim.write_text("owner data\n", encoding="utf-8")
        output = self.root / "signed-link.json"
        output.symlink_to(victim.name)
        with (
            patch(
                "sddgov.owner_approval._ssh_agent_exchange",
                side_effect=self._agent_exchange,
            ),
            self.assertRaises((FileExistsError, ValueError)),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        self.assertEqual(victim.read_text(encoding="utf-8"), "owner data\n")
        self.assertTrue(output.is_symlink())

    def test_signed_receipt_never_reports_approval_for_a_replaced_parent(self):
        output = self.root / "owner-outbox" / "receipt.json"
        parked = self.root / "parked-owner-outbox"
        replacement = b"later writer\n"
        real_require = fs_security.require_directory_path_identity
        swapped = False

        def replace_parent(path, descriptor, label):
            nonlocal swapped
            if not swapped:
                output.parent.rename(parked)
                output.parent.mkdir()
                output.write_bytes(replacement)
                swapped = True
            real_require(path, descriptor, label)

        with (
            patch(
                "sddgov.owner_approval._ssh_agent_exchange",
                side_effect=self._agent_exchange,
            ),
            patch(
                "sddgov.fs_security.require_directory_path_identity",
                side_effect=replace_parent,
            ),
            self.assertRaisesRegex(ValueError, "changed during operation"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        self.assertTrue(swapped)
        self.assertEqual(output.read_bytes(), replacement)
        self.assertFalse((parked / "receipt.json").exists())

    def test_agent_cli_only_renders_and_never_exposes_a_signing_command(self):
        parser = build_agent_parser()
        with (
            redirect_stderr(StringIO()),
            self.assertRaises(SystemExit) as rejected,
        ):
            parser.parse_args(["decision", "approve-product"])
        self.assertEqual(rejected.exception.code, 3)

        args = parser.parse_args(
            [
                "decision",
                "show-product-approval",
                "work-packages/DEC-SYNTHETIC.request.json",
                "--path",
                str(self.root),
            ]
        )
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(run_agent_cli(args), 0)
        rendered = json.loads(output.getvalue())
        self.assertEqual(rendered["state"], "ACTION_REQUIRED")
        self.assertEqual(rendered["approval_card"]["decision_id"], "DEC-SYNTHETIC")

    def test_owner_cli_declines_without_json_or_key_arguments(self):
        args = build_owner_parser().parse_args(
            [
                "approve-product",
                "work-packages/DEC-SYNTHETIC.request.json",
                "--output",
                str(self.root / "must-not-exist.json"),
                "--path",
                str(self.root),
            ]
        )
        output = StringIO()
        with (
            patch("sddgov.owner_cli._read_owner_choice", return_value="B") as choice,
            redirect_stdout(output),
        ):
            self.assertEqual(run_owner_cli(args), 1)
        rendered = choice.call_args.args[1]
        self.assertIn("SDG OWNER DECISION", rendered)
        self.assertIn("Approver identity: synthetic-owner", rendered)
        self.assertIn("Owner client: SDG", rendered)
        self.assertNotIn("SDG OWNER DECISION", output.getvalue())
        self.assertIn('"state": "DECLINED"', output.getvalue())
        self.assertFalse((self.root / "must-not-exist.json").exists())

        for forbidden in ("--assumption", "--approver-id", "--valid-days"):
            with (
                redirect_stderr(StringIO()),
                self.assertRaises(SystemExit) as rejected,
            ):
                build_owner_parser().parse_args(
                    [
                        "approve-product",
                        "work-packages/DEC-SYNTHETIC.request.json",
                        forbidden,
                        "attacker-value",
                    ]
                )
            self.assertEqual(rejected.exception.code, 3)

    def test_owner_choice_card_is_written_only_to_the_controlling_terminal(self):
        _request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        rendered = render_product_approval_card(card)

        class Terminal:
            def __init__(self):
                self.output = StringIO()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def write(self, value):
                return self.output.write(value)

            def readline(self):
                return "A\n"

        terminal = Terminal()
        standard_output = StringIO()
        with (
            patch("builtins.open", return_value=terminal) as opened,
            redirect_stdout(standard_output),
        ):
            self.assertEqual(_read_owner_choice(card, rendered), "A")
        opened.assert_called_once_with(
            "/dev/tty", "r+", encoding="utf-8", buffering=1
        )
        self.assertIn("SDG OWNER DECISION", terminal.output.getvalue())
        self.assertEqual(standard_output.getvalue(), "")

    def test_signed_receipt_is_bound_to_repository_and_trust_domain(self):
        output = self.root / "audience-bound.json"
        with patch(
            "sddgov.owner_approval._ssh_agent_exchange",
            side_effect=self._agent_exchange,
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        envelope = json.loads(output.read_text(encoding="utf-8"))
        self.assertNotIn("repository_id", envelope["receipt"])
        self.assertNotIn("trust_domain", envelope["receipt"])
        with (
            patch(
                "sddgov.autonomy._repository_identity",
                return_value="github.com/example/different",
            ),
            self.assertRaisesRegex(ValueError, "not authorized for this repository"),
        ):
            _verify_product_envelope(self.root, envelope)

        self.domain["bindings"][0]["repository_root"] = str(
            self.root / "different-repository-root"
        )
        with self.assertRaisesRegex(ValueError, "not authorized for this repository root"):
            _verify_product_envelope(self.root, envelope)

    def test_owner_runtime_rejects_python_injection_checkout_and_non_venv(self):
        prefix = self.root / "owner-venv"
        executable = prefix / "bin" / "python"
        module = prefix / "lib" / "python3.12" / "site-packages" / "sddgov" / "owner_cli.py"
        invocation = prefix / "bin" / "sddgov-owner"
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sddgov.owner_cli.sys.prefix", str(prefix)),
            patch("sddgov.owner_cli.sys.base_prefix", "/usr"),
            patch("sddgov.owner_cli.sys.executable", str(executable)),
            patch("sddgov.owner_cli.sys.argv", [str(invocation)]),
            patch("sddgov.owner_cli.__file__", str(module)),
        ):
            _require_owner_runtime(self.root)

            with (
                patch.dict(os.environ, {"PYTHONPATH": "/attacker"}),
                self.assertRaisesRegex(ValueError, "PYTHONPATH"),
            ):
                _require_owner_runtime(self.root)

            with (
                patch("sddgov.owner_cli.sys.base_prefix", str(prefix)),
                self.assertRaisesRegex(ValueError, "virtual environment"),
            ):
                _require_owner_runtime(self.root)

            with (
                patch("sddgov.owner_cli.Path.cwd", return_value=self.root),
                self.assertRaisesRegex(ValueError, "outside the Agent repository"),
            ):
                _require_owner_runtime(self.root)


if __name__ == "__main__":
    unittest.main()
