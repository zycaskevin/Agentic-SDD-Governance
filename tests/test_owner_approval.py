import base64
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

from sddgov.autonomy import _read_repository_regular_file, _verify_product_envelope
from sddgov.governance import init_project
from sddgov.cli import build_parser as build_agent_parser, run as run_agent_cli
from sddgov.owner_cli import build_parser as build_owner_parser, run as run_owner_cli
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
        self.assumption.write_text(
            "# Exact bounded authority decision\n\nNo Production operation is authorized.\n",
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
        self.trust_loader = patch(
            "sddgov.autonomy.load_control_plane_json",
            return_value=self.trust,
        )
        self.trust_loader.start()
        self.addCleanup(self.trust_loader.stop)

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
        rendered = render_product_approval_card(card)
        self.assertIn("SDG OWNER DECISION", rendered)
        self.assertIn("[A] Approve the exact bounded authority contract.", rendered)
        self.assertNotIn("sha256", rendered.lower())

    def test_recommended_choice_uses_agent_key_and_writes_verified_receipt(self):
        output = self.root / "out" / "signed-product-approval.json"
        with patch(
            "sddgov.owner_approval._ssh_agent_exchange",
            side_effect=self._agent_exchange,
        ):
            result = approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                ["work-packages/DEC-SYNTHETIC.md"],
                "synthetic-owner",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
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
                ["work-packages/DEC-SYNTHETIC.md"],
                "synthetic-owner",
                "B",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
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
                ["work-packages/DEC-SYNTHETIC.md"],
                "synthetic-owner",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
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
                ["work-packages/DEC-SYNTHETIC.md"],
                "synthetic-owner",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
            )
        self.assertEqual(victim.read_text(encoding="utf-8"), "owner data\n")
        self.assertTrue(output.is_symlink())

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
                "--assumption",
                "work-packages/DEC-SYNTHETIC.md",
                "--approver-id",
                "synthetic-owner",
                "--output",
                str(self.root / "must-not-exist.json"),
                "--path",
                str(self.root),
            ]
        )
        output = StringIO()
        with (
            patch("sddgov.owner_cli._read_owner_choice", return_value="B"),
            redirect_stdout(output),
        ):
            self.assertEqual(run_owner_cli(args), 1)
        self.assertIn("SDG OWNER DECISION", output.getvalue())
        self.assertIn('"state": "DECLINED"', output.getvalue())
        self.assertFalse((self.root / "must-not-exist.json").exists())


if __name__ == "__main__":
    unittest.main()
