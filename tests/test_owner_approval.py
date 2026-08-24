import base64
import copy
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import sddgov.fs_security as fs_security
from sddgov.trust import load_control_plane_json
from sddgov.autonomy import (
    _canonical_receipt,
    _read_repository_regular_file,
    _verify_product_envelope,
)
from sddgov.governance import init_project
from sddgov.cli import build_parser as build_agent_parser, run as run_agent_cli
from sddgov.owner_cli import (
    _canonical_distribution_target,
    _parse_exact_entry_points,
    _require_record_sha256,
    _read_owner_choice,
    _require_owner_distribution,
    _require_isolated_venv_config,
    _require_owner_runtime,
    build_parser as build_owner_parser,
    main as owner_main,
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
        self.root = fs_security.canonicalize_platform_path(
            Path(self.temporary.name)
        )
        self.root.chmod(0o2750)
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
                    "assumption_paths": [
                        "work-packages/DEC-SYNTHETIC.md",
                        "work-packages/DEC-SYNTHETIC.request.json",
                    ],
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
        self.owner_trust_loader = patch(
            "sddgov.owner_approval.load_owner_runtime_control_plane_json",
            side_effect=lambda _path, label: (
                self.domain if "domain" in label else self.trust
            ),
        )
        self.owner_trust_loader_mock = self.owner_trust_loader.start()
        self.addCleanup(self.owner_trust_loader.stop)
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
        self.assertEqual(
            card["assumption_paths"],
            [
                "work-packages/DEC-SYNTHETIC.md",
                "work-packages/DEC-SYNTHETIC.request.json",
            ],
        )
        self.assertEqual(card["repository_id"], "github.com/example/synthetic")
        self.assertEqual(card["trust_domain"], "synthetic-test-domain")
        rendered = render_product_approval_card(card)
        self.assertIn("SDG OWNER DECISION", rendered)
        self.assertIn("[A] Approve the exact bounded authority contract.", rendered)
        self.assertNotIn("sha256", rendered.lower())

    def test_card_rejects_a_self_assumption_over_the_per_artifact_bound(self):
        request_raw = self.request.read_bytes()
        self.assertLess(len(request_raw), 256 * 1024)
        self.request.write_bytes(
            request_raw + b" " * (300 * 1024 - len(request_raw))
        )

        with self.assertRaisesRegex(ValueError, "exceeds the bounded size"):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )

    def test_owner_card_uses_the_separate_owner_runtime_trust_loader(self):
        _request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        self.assertEqual(card["approver_id"], "synthetic-owner")
        labels = [
            call.args[1]
            for call in self.owner_trust_loader_mock.mock_calls
            if len(call.args) == 2
        ]
        self.assertIn("fixed trusted approver store", labels)
        self.assertIn("fixed trusted approver domain store", labels)

    def test_root_owner_card_reads_fixed_trust_without_weakening_agent_loader(self):
        control_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(control_temporary.cleanup)
        control_root = Path(control_temporary.name)
        trust_path = control_root / "trusted-approvers.json"
        domain_path = control_root / "trusted-approver-domains.json"
        trust_path.write_text(json.dumps(self.trust), encoding="utf-8")
        domain_path.write_text(json.dumps(self.domain), encoding="utf-8")
        real_stat = os.stat
        real_fstat = os.fstat

        def as_root_owned(metadata):
            values = list(metadata)
            values[0] = metadata.st_mode & ~0o022
            values[4] = 0
            return os.stat_result(values)

        self.owner_trust_loader.stop()
        try:
            with (
                patch("sddgov.trust.TRUSTED_APPROVERS_FILE", trust_path),
                patch("sddgov.trust.TRUSTED_APPROVER_DOMAINS_FILE", domain_path),
                patch("sddgov.trust.os.geteuid", return_value=0),
                patch(
                    "sddgov.trust.os.stat",
                    side_effect=lambda *args, **kwargs: as_root_owned(
                        real_stat(*args, **kwargs)
                    ),
                ),
                patch(
                    "sddgov.trust.os.fstat",
                    side_effect=lambda descriptor: as_root_owned(
                        real_fstat(descriptor)
                    ),
                ),
            ):
                _request, card = build_product_approval_card(
                    self.root,
                    "work-packages/DEC-SYNTHETIC.request.json",
                )
                self.assertEqual(card["approver_id"], "synthetic-owner")
                with self.assertRaisesRegex(ValueError, "Agent runs as root"):
                    load_control_plane_json(trust_path, "Agent trust")
        finally:
            self.owner_trust_loader_mock = self.owner_trust_loader.start()

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
                    "work-packages/DEC-SYNTHETIC.request.json",
                ],
                "unique and canonically sorted",
            ),
            (
                [
                    "work-packages/DEC-SYNTHETIC.request.json",
                    "work-packages/DEC-SYNTHETIC.md",
                ],
                "unique and canonically sorted",
            ),
            (["../DEC-SYNTHETIC.md"], "canonical repository-relative"),
            (["work-packages/DEC-\x1b[2J.md"], "canonical repository-relative"),
            (["work-packages/DEC-\rspoof.md"], "canonical repository-relative"),
            (["work-packages/DEC-\nspoof.md"], "canonical repository-relative"),
            (["work-packages/DEC-\u202espoof.md"], "canonical repository-relative"),
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

        marker_line = next(
            line
            for line in original_assumption.splitlines()
            if line.startswith("Owner client binding: ")
        )
        self.assumption.write_text(
            original_assumption + marker_line + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "assumptions must bind one exact"):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )

        second = self.root / "work-packages" / "DEC-SYNTHETIC-SECOND.md"
        second.write_text(marker_line + "\n", encoding="utf-8")
        cross_artifact = copy.deepcopy(original_request)
        cross_artifact["assumption_paths"] = [
            "work-packages/DEC-SYNTHETIC-SECOND.md",
            "work-packages/DEC-SYNTHETIC.md",
            "work-packages/DEC-SYNTHETIC.request.json",
        ]
        self.request.write_text(json.dumps(cross_artifact), encoding="utf-8")
        self.assumption.write_text(original_assumption, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "assumptions must bind one exact"):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )

        second.write_text(marker_line + "-near-match\n", encoding="utf-8")
        build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        second.unlink()
        self.request.write_text(json.dumps(original_request), encoding="utf-8")
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

        non_approvable = copy.deepcopy(original)
        non_approvable["decision_package"]["recommended"] = "B"
        self.request.write_text(json.dumps(non_approvable), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "only approvable option"):
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

        _request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        for hostile_version in ("0.2.0\x1b[2J", "0.2.0\rspoof", "0.2.0\u202e"):
            hostile_card = copy.deepcopy(card)
            hostile_card["owner_client"]["version"] = hostile_version
            with self.subTest(hostile_version=repr(hostile_version)), self.assertRaisesRegex(
                ValueError, "terminal control|invisible"
            ):
                render_product_approval_card(hostile_card)

    def test_owner_request_rejects_recursive_duplicate_json_members(self):
        original = self.request.read_text(encoding="utf-8")
        cases = (
            original.replace("{", '{"decision_id":"DECOY",', 1),
            original.replace(
                '"decision_package": {',
                '"decision_package": {"risk_level":"L1",',
                1,
            ),
            original.replace('"label": "A",', '"label":"X","label":"A",', 1),
            original.replace(
                '"owner_client": {',
                '"owner_client": {"version":"DECOY",',
                1,
            ),
        )
        for raw in cases:
            with self.subTest(raw=raw[:80]):
                self.request.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "duplicate member"):
                    build_product_approval_card(
                        self.root,
                        "work-packages/DEC-SYNTHETIC.request.json",
                    )
        self.request.write_text(original, encoding="utf-8")

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
        paths.append("work-packages/DEC-SYNTHETIC.request.json")
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
        output.parent.mkdir()
        output.parent.chmod(0o2750)
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
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o640)
        envelope = json.loads(output.read_text(encoding="utf-8"))
        receipt, digest = _verify_product_envelope(self.root, envelope)
        self.assertEqual(receipt["decision_id"], "DEC-SYNTHETIC")
        self.assertTrue(receipt["summary"].startswith("Approved option A:"))
        self.assertEqual(result["receipt_sha256"], digest)

    def test_owner_sign_and_final_verification_never_use_the_agent_loader(self):
        output = self.root / "owner-only-final-verification.json"
        self.owner_trust_loader_mock.reset_mock()
        with (
            patch(
                "sddgov.autonomy.load_control_plane_json",
                side_effect=AssertionError("Agent loader must remain unused"),
            ) as agent_loader,
            patch(
                "sddgov.owner_approval._ssh_agent_exchange",
                side_effect=self._agent_exchange,
            ),
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
        agent_loader.assert_not_called()
        labels = [
            call.args[1]
            for call in self.owner_trust_loader_mock.mock_calls
            if len(call.args) == 2
        ]
        self.assertGreaterEqual(labels.count("fixed trusted approver store"), 3)
        self.assertGreaterEqual(labels.count("fixed trusted approver domain store"), 3)

    def test_owner_existing_receipt_reuse_never_uses_the_agent_loader(self):
        output = self.root / "owner-only-existing-verification.json"
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

        self.owner_trust_loader_mock.reset_mock()
        with (
            patch(
                "sddgov.autonomy.load_control_plane_json",
                side_effect=AssertionError("Agent loader must remain unused"),
            ) as agent_loader,
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
        ):
            result = approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        self.assertTrue(result["already_committed"])
        agent_loader.assert_not_called()
        exchange.assert_not_called()
        labels = [
            call.args[1]
            for call in self.owner_trust_loader_mock.mock_calls
            if len(call.args) == 2
        ]
        self.assertGreaterEqual(labels.count("fixed trusted approver store"), 2)
        self.assertGreaterEqual(labels.count("fixed trusted approver domain store"), 2)

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
            self.assertRaisesRegex(ValueError, "changed while being read"),
        ):
            _read_repository_regular_file(
                self.root,
                PurePosixPath("work-packages/DEC-SYNTHETIC.md"),
                max_bytes=1024,
            )
        self.assertTrue(changed)

    def test_card_inputs_reject_between_read_parent_generation_changes(self):
        work_packages = self.root / "work-packages"
        parked = self.root / "work-packages-parked"
        original_read = fs_security.FileSetSnapshot.read
        swapped = False

        def read_then_swap(snapshot, relative, *, max_bytes):
            nonlocal swapped
            raw = original_read(snapshot, relative, max_bytes=max_bytes)
            if (
                not swapped
                and snapshot.label == "product approval card inputs"
                and str(relative).endswith("DEC-SYNTHETIC.request.json")
            ):
                work_packages.rename(parked)
                shutil.copytree(parked, work_packages)
                swapped = True
            return raw

        with (
            patch(
                "sddgov.owner_approval.FileSetSnapshot.read",
                new=read_then_swap,
            ),
            self.assertRaisesRegex(ValueError, "directory set changed"),
        ):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )
        self.assertTrue(swapped)

    def test_card_inputs_reject_same_bytes_leaf_replacement_after_read(self):
        original_read = fs_security.FileSetSnapshot.read
        replaced = False

        def read_then_replace(snapshot, relative, *, max_bytes):
            nonlocal replaced
            raw = original_read(snapshot, relative, max_bytes=max_bytes)
            if (
                not replaced
                and snapshot.label == "product approval card inputs"
                and str(relative).endswith("DEC-SYNTHETIC.request.json")
            ):
                replacement = self.request.with_suffix(".replacement")
                replacement.write_bytes(raw)
                os.replace(replacement, self.request)
                replaced = True
            return raw

        with (
            patch(
                "sddgov.owner_approval.FileSetSnapshot.read",
                new=read_then_replace,
            ),
            self.assertRaisesRegex(ValueError, "file set changed"),
        ):
            build_product_approval_card(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
            )
        self.assertTrue(replaced)

    def test_owner_client_identity_is_one_call_wide_source_snapshot(self):
        package = self.root / "installed-owner-client" / "sddgov"
        package.mkdir(parents=True)
        names = (
            "__init__.py",
            "autonomy.py",
            "fs_security.py",
            "governance.py",
            "owner_approval.py",
            "owner_cli.py",
            "owner_launcher.sh",
            "trust.py",
        )
        for name in names:
            (package / name).write_text(f"reviewed {name}\n", encoding="utf-8")
        original_read = fs_security.FileSetSnapshot.read
        replaced = False

        def read_then_replace(snapshot, relative, *, max_bytes):
            nonlocal replaced
            raw = original_read(snapshot, relative, max_bytes=max_bytes)
            if (
                not replaced
                and snapshot.label == "Owner client package"
                and str(relative) == "__init__.py"
            ):
                replacement = package / ".replacement"
                replacement.write_bytes(raw)
                os.replace(replacement, package / "__init__.py")
                replaced = True
            return raw

        with (
            patch("sddgov.owner_approval.__file__", str(package / "owner_approval.py")),
            patch(
                "sddgov.owner_approval.FileSetSnapshot.read",
                new=read_then_replace,
            ),
            self.assertRaisesRegex(ValueError, "file set changed"),
        ):
            _owner_client_identity()
        self.assertTrue(replaced)

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
            self.assertRaisesRegex(ValueError, "Owner signer channel is unavailable"),
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
            self.assertRaisesRegex(ValueError, "Owner signer channel is unavailable"),
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

    def test_owner_outbox_must_be_preprovisioned_and_not_group_writable(self):
        card_digest = self._card_sha256()
        missing = self.root / "missing-owner-outbox" / "receipt.json"
        with (
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            self.assertRaisesRegex(ValueError, "must be pre-provisioned"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                missing,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=card_digest,
            )
        exchange.assert_not_called()

        private_parent = self.root / "private-owner-outbox"
        private_parent.mkdir(mode=0o700)
        private_parent.chmod(0o700)
        with (
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            self.assertRaisesRegex(ValueError, "one-way handoff"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                private_parent / "receipt.json",
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=card_digest,
            )
        exchange.assert_not_called()

        unsafe_parent = self.root / "writable-owner-outbox"
        unsafe_parent.mkdir(mode=0o770)
        unsafe_parent.chmod(0o770)
        with (
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            self.assertRaisesRegex(ValueError, "one-way handoff"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                unsafe_parent / "receipt.json",
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=card_digest,
            )
        exchange.assert_not_called()

    def test_signed_receipt_never_reports_approval_for_a_replaced_parent(self):
        output = self.root / "owner-outbox" / "receipt.json"
        output.parent.mkdir()
        output.parent.chmod(0o2750)
        parked = self.root / "parked-owner-outbox"
        replacement = b"later writer\n"
        real_require = fs_security.require_directory_path_identity
        swapped = False

        def replace_parent(path, descriptor, label):
            nonlocal swapped
            if not swapped and Path(path) == output.parent:
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
        self.assertEqual(output.getvalue(), "")
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

    def test_owner_cli_never_echoes_hostile_argv_or_filesystem_errors(self):
        hostile = "\x1b[2J\u202espoof"
        cases = (
            ["sddgov-owner", hostile],
            [
                "sddgov-owner",
                "approve-product",
                "work-packages/DEC-SYNTHETIC.request.json",
                "--output",
                str(self.root / hostile),
                "--path",
                str(self.root),
            ],
        )
        for argv in cases:
            with self.subTest(argv=argv), patch.object(sys, "argv", argv):
                stderr = StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as stopped:
                    owner_main()
                self.assertEqual(stopped.exception.code, 3)
                self.assertNotIn("\x1b", stderr.getvalue())
                self.assertNotIn("\u202e", stderr.getvalue())
                self.assertNotIn("spoof", stderr.getvalue())

        safe_argv = [
            "sddgov-owner",
            "approve-product",
            "work-packages/DEC-SYNTHETIC.request.json",
            "--output",
            str(self.root / "receipt.json"),
            "--path",
            str(self.root),
        ]
        with (
            patch.object(sys, "argv", safe_argv),
            patch(
                "sddgov.owner_cli._require_owner_runtime",
                side_effect=OSError(2, "synthetic", hostile),
            ),
        ):
            stderr = StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as stopped:
                owner_main()
            self.assertEqual(stopped.exception.code, 3)
            self.assertEqual(stderr.getvalue(), "[ERROR] Owner approval failed closed.\n")

    def test_owner_cli_commit_is_not_reversed_or_repeated_by_stdout_failure(self):
        output = self.root / "committed-owner-receipt.json"
        args = build_owner_parser().parse_args(
            [
                "approve-product",
                "work-packages/DEC-SYNTHETIC.request.json",
                "--output",
                str(output),
                "--path",
                str(self.root),
            ]
        )

        class BrokenOutput(StringIO):
            def write(self, _value):
                raise BrokenPipeError("synthetic broken stdout")

        with (
            patch("sddgov.owner_cli._read_owner_choice", return_value="A"),
            patch(
                "sddgov.owner_approval._ssh_agent_exchange",
                side_effect=self._agent_exchange,
            ),
            redirect_stdout(BrokenOutput()),
        ):
            self.assertEqual(run_owner_cli(args), 0)
        self.assertTrue(output.exists())

        with (
            patch("sddgov.owner_cli._read_owner_choice") as choice,
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            redirect_stdout(BrokenOutput()),
        ):
            self.assertEqual(run_owner_cli(args), 0)
        choice.assert_not_called()
        exchange.assert_not_called()

    def test_existing_receipt_requires_the_exact_displayed_validity_window(self):
        output = self.root / "validity-bound-owner-receipt.json"
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
        issued_at = datetime.fromisoformat(
            envelope["receipt"]["issued_at"].replace("Z", "+00:00")
        )
        envelope["receipt"]["expires_at"] = (
            issued_at + timedelta(days=31)
        ).isoformat().replace("+00:00", "Z")
        envelope["signature"] = base64.b64encode(
            self.private_key.sign(_canonical_receipt(envelope["receipt"]))
        ).decode("ascii")
        output.write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with (
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            self.assertRaisesRegex(ValueError, "validity differs from the displayed card"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        exchange.assert_not_called()

    def test_existing_receipt_requires_owner_owned_single_link_public_mode(self):
        output = self.root / "protected-existing-owner-receipt.json"
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

        output.chmod(0o600)
        with (
            patch("sddgov.owner_approval._ssh_agent_exchange") as exchange,
            self.assertRaisesRegex(ValueError, "unsafe ownership or mode"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        exchange.assert_not_called()

        output.chmod(0o640)
        hardlink = output.with_name("receipt-hardlink.json")
        os.link(output, hardlink)
        with self.assertRaisesRegex(ValueError, "unsafe ownership or mode"):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )
        hardlink.unlink()

        real_stat = os.stat

        def foreign_leaf(path, *args, **kwargs):
            metadata = real_stat(path, *args, **kwargs)
            if path == output.name and kwargs.get("dir_fd") is not None:
                values = list(metadata)
                values[stat.ST_UID] = metadata.st_uid + 1
                return os.stat_result(values)
            return metadata

        with (
            patch("sddgov.owner_approval.os.stat", side_effect=foreign_leaf),
            self.assertRaisesRegex(ValueError, "unsafe ownership or mode"),
        ):
            approve_product_decision(
                self.root,
                "work-packages/DEC-SYNTHETIC.request.json",
                "A",
                output,
                ssh_auth_sock="/synthetic/confirmed-agent.sock",
                expected_card_sha256=self._card_sha256(),
            )

    def test_owner_choice_card_is_written_only_to_the_controlling_terminal(self):
        _request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        rendered = render_product_approval_card(card)

        master_fd, slave_fd = os.openpty()
        self.addCleanup(os.close, master_fd)
        self.addCleanup(os.close, slave_fd)
        standard_output = StringIO()
        with (
            patch(
                "sddgov.owner_cli.os.open",
                side_effect=lambda *_args, **_kwargs: os.dup(slave_fd),
            ) as opened,
            patch("sddgov.owner_cli.os.tcgetpgrp", return_value=os.getpgrp()),
            patch("sddgov.owner_cli.os.read", return_value=b"A\n"),
            redirect_stdout(standard_output),
        ):
            self.assertEqual(_read_owner_choice(card, rendered), "A")
        self.assertEqual(opened.call_count, 1)
        terminal_output = os.read(master_fd, 32768).decode("utf-8", errors="replace")
        self.assertIn("SDG OWNER DECISION", terminal_output)
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
        (prefix / "bin").mkdir(parents=True)
        (prefix / "pyvenv.cfg").write_text(
            "home = /usr/bin\ninclude-system-site-packages = false\n",
            encoding="utf-8",
        )
        package = prefix / "lib" / "python3.12" / "site-packages" / "sddgov"
        package.mkdir(parents=True)
        executable = prefix / "bin" / "python"
        executable.symlink_to(Path(sys.executable))
        module = package / "owner_cli.py"
        module.write_text("# installed module\n", encoding="utf-8")
        invocation = prefix / "bin" / "sddgov-owner"
        launcher_source = Path(__file__).resolve().parents[1] / "scripts" / "sddgov-owner"
        invocation.write_bytes(launcher_source.read_bytes())
        invocation.chmod(0o755)
        (package / "owner_launcher.sh").write_bytes(launcher_source.read_bytes())
        for directory in (
            prefix,
            prefix / "bin",
            prefix / "lib",
            prefix / "lib" / "python3.12",
            prefix / "lib" / "python3.12" / "site-packages",
            package,
        ):
            directory.chmod(0o755)
        for regular in (
            prefix / "pyvenv.cfg",
            module,
            package / "owner_launcher.sh",
        ):
            regular.chmod(0o644)
        with (
            patch.dict(
                os.environ,
                {"SDDGOV_OWNER_ISOLATED_LAUNCHER": str(invocation)},
                clear=True,
            ),
            patch("sddgov.owner_cli.sys.prefix", str(prefix)),
            patch("sddgov.owner_cli.sys.base_prefix", "/usr"),
            patch("sddgov.owner_cli.sys.executable", str(executable)),
            patch("sddgov.owner_cli.sys.argv", [str(invocation)]),
            patch("sddgov.owner_cli.sys.flags", SimpleNamespace(isolated=1)),
            patch("sddgov.owner_cli.__file__", str(module)),
            patch("sddgov.owner_cli._require_isolated_runtime_paths"),
            patch("sddgov.owner_cli._require_owner_distribution") as distribution,
        ):
            _require_owner_runtime(self.root)
            distribution.assert_called_once()

            with (
                patch.dict(os.environ, {"PYTHONPATH": "/attacker"}),
                self.assertRaisesRegex(ValueError, "injection"),
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

    def test_owner_distribution_rejects_duplicate_record_paths(self):
        prefix = self.root / "record-venv"
        distribution_root = prefix / "lib" / "python3.12" / "site-packages"
        target = distribution_root / "sddgov" / "owner_cli.py"
        target.parent.mkdir(parents=True)
        target.write_text("# owner client\n", encoding="utf-8")
        for directory in (
            prefix,
            prefix / "lib",
            prefix / "lib" / "python3.12",
            distribution_root,
            target.parent,
        ):
            directory.chmod(0o755)
        target.chmod(0o644)

        class RecordRow:
            def __str__(self):
                return "sddgov/owner_cli.py"

            def locate(self):
                return target

        distribution = SimpleNamespace(
            files=[RecordRow(), RecordRow()],
            entry_points=[],
            locate_file=lambda _path: distribution_root,
            metadata={"Name": "agentic-sdd-governance"},
            version="0.2.0rc1",
        )
        with (
            patch(
                "sddgov.owner_cli.importlib_metadata.distributions",
                return_value=[distribution],
            ),
            patch(
                "sddgov.owner_cli._owner_client_identity",
                return_value={"version": "0.2.0rc1", "source_files": []},
            ),
            self.assertRaisesRegex(ValueError, "duplicate targets"),
        ):
            _require_owner_distribution(
                prefix,
                target,
                prefix / "bin" / "sddgov-owner",
                b"launcher",
            )

    def test_owner_distribution_requires_one_unique_normalized_install(self):
        duplicate = SimpleNamespace(
            files=[],
            metadata={"Name": "agentic_sdd.governance"},
        )
        with (
            patch(
                "sddgov.owner_cli.importlib_metadata.distributions",
                return_value=[duplicate, duplicate],
            ),
            self.assertRaisesRegex(ValueError, "one unique installed distribution"),
        ):
            _require_owner_distribution(
                self.root,
                self.root / "sddgov" / "owner_cli.py",
                self.root / "bin" / "sddgov-owner",
                b"launcher",
            )

    def test_owner_entry_point_metadata_rejects_duplicate_rows(self):
        valid = (
            b"[console_scripts]\n"
            b"evidence = sddgov.cli:evidence_main\n"
            b"sddgov = sddgov.cli:main\n"
        )
        self.assertEqual(
            _parse_exact_entry_points(valid),
            [
                ("console_scripts", "evidence", "sddgov.cli:evidence_main"),
                ("console_scripts", "sddgov", "sddgov.cli:main"),
            ],
        )
        for raw in (
            valid + b"evidence = sddgov.cli:evidence_main\n",
            valid + b"[console_scripts]\n",
        ):
            with self.assertRaisesRegex(ValueError, "metadata is invalid"):
                _parse_exact_entry_points(raw)

    def test_owner_launcher_record_requires_explicit_sha256_hash(self):
        expected = "a" * 43
        for row in (
            SimpleNamespace(hash=None),
            SimpleNamespace(
                hash=SimpleNamespace(mode="sha512", value=expected)
            ),
            SimpleNamespace(
                hash=SimpleNamespace(mode="sha256", value="b" * 43)
            ),
        ):
            with self.assertRaisesRegex(ValueError, "not hash-bound"):
                _require_record_sha256(row, expected, "Owner isolated launcher")
        _require_record_sha256(
            SimpleNamespace(
                hash=SimpleNamespace(mode="sha256", value=expected)
            ),
            expected,
            "Owner isolated launcher",
        )

    def test_owner_distribution_rejects_source_and_launcher_alias_rows(self):
        prefix = self.root / "canonical-record-venv"
        distribution_root = prefix / "lib" / "python3.12" / "site-packages"
        source = distribution_root / "sddgov" / "owner_cli.py"
        launcher = prefix / "bin" / "sddgov-owner"
        source.parent.mkdir(parents=True)
        launcher.parent.mkdir(parents=True)
        source.write_text("# source\n", encoding="utf-8")
        launcher.write_text("#!/bin/sh\n", encoding="utf-8")
        for directory in (
            prefix,
            prefix / "bin",
            prefix / "lib",
            prefix / "lib" / "python3.12",
            distribution_root,
            source.parent,
        ):
            directory.chmod(0o755)
        source.chmod(0o644)
        launcher.chmod(0o755)
        allowed = {"../../../bin/sddgov-owner"}

        resolved, _identity = _canonical_distribution_target(
            "../../../bin/sddgov-owner",
            distribution_root,
            prefix,
            launcher,
            allowed,
        )
        self.assertEqual(resolved, launcher.resolve())
        for name, target in (
            ("sddgov/../sddgov/owner_cli.py", source),
            ("../../../bin/../bin/sddgov-owner", launcher),
        ):
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "noncanonical path"
            ):
                _canonical_distribution_target(
                    name,
                    distribution_root,
                    prefix,
                    target,
                    allowed,
                )

    def test_owner_venv_config_requires_one_exact_false_setting(self):
        _require_isolated_venv_config(
            b"home = /usr/bin\ninclude-system-site-packages = false\n"
        )
        for raw, message in (
            (
                b"include-system-site-packages = false\n"
                b"include-system-site-packages = true\n",
                "duplicate settings",
            ),
            (b"include-system-site-packages = true\n", "exclude system site"),
            (b"include-system-site-packages\n", "malformed setting"),
            (b"include-system-site-packages = \xff\n", "must be UTF-8"),
        ):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, message):
                _require_isolated_venv_config(raw)

    def test_isolated_launcher_ignores_hostile_pythonpath_before_package_import(self):
        launcher_root = self.root / "isolated-launcher"
        bin_dir = launcher_root / "bin"
        bin_dir.mkdir(parents=True)
        launcher = bin_dir / "sddgov-owner"
        launcher.write_bytes(
            (Path(__file__).resolve().parents[1] / "scripts" / "sddgov-owner").read_bytes()
        )
        launcher.chmod(0o755)
        (bin_dir / "python").symlink_to(Path(sys.executable))
        hostile = self.root / "hostile-pythonpath" / "sddgov"
        hostile.mkdir(parents=True)
        marker = self.root / "hostile-imported"
        (hostile / "__init__.py").write_text("", encoding="utf-8")
        (hostile / "owner_cli.py").write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(launcher), "--help"],
            cwd=self.root,
            env={**os.environ, "PYTHONPATH": str(hostile.parent)},
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())

    def test_owner_choice_uses_a_real_bounded_pty_line(self):
        _request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        rendered = render_product_approval_card(card)
        master_fd, slave_fd = os.openpty()
        self.addCleanup(os.close, master_fd)
        self.addCleanup(os.close, slave_fd)
        os.write(master_fd, b"A\n")
        reads = iter((b"A", b"\n"))
        with (
            patch(
                "sddgov.owner_cli.os.open",
                side_effect=lambda *_args, **_kwargs: os.dup(slave_fd),
            ),
            patch("sddgov.owner_cli.os.tcgetpgrp", return_value=os.getpgrp()),
            patch(
                "sddgov.owner_cli.os.read",
                side_effect=lambda descriptor, size: next(reads),
            ),
        ):
            self.assertEqual(_read_owner_choice(card, rendered), "A")

    def test_owner_choice_rejects_an_unbounded_line(self):
        _request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )

        master_fd, slave_fd = os.openpty()
        self.addCleanup(os.close, master_fd)
        self.addCleanup(os.close, slave_fd)
        os.write(master_fd, b"AAA\n")
        with (
            patch(
                "sddgov.owner_cli.os.open",
                side_effect=lambda *_args, **_kwargs: os.dup(slave_fd),
            ),
            patch("sddgov.owner_cli.os.tcgetpgrp", return_value=os.getpgrp()),
            self.assertRaisesRegex(ValueError, "bounded A or B"),
        ):
            _read_owner_choice(card, render_product_approval_card(card))

    def test_owner_choice_rejects_regular_and_background_devices(self):
        _request, card = build_product_approval_card(
            self.root,
            "work-packages/DEC-SYNTHETIC.request.json",
        )
        rendered = render_product_approval_card(card)
        regular = self.root / "not-a-terminal"
        regular.write_bytes(b"A\n")
        regular_fd = os.open(regular, os.O_RDWR)
        self.addCleanup(os.close, regular_fd)
        with (
            patch(
                "sddgov.owner_cli.os.open",
                side_effect=lambda *_args, **_kwargs: os.dup(regular_fd),
            ),
            self.assertRaisesRegex(ValueError, "character controlling terminal"),
        ):
            _read_owner_choice(card, rendered)

        master_fd, slave_fd = os.openpty()
        self.addCleanup(os.close, master_fd)
        self.addCleanup(os.close, slave_fd)
        with (
            patch(
                "sddgov.owner_cli.os.open",
                side_effect=lambda *_args, **_kwargs: os.dup(slave_fd),
            ),
            patch(
                "sddgov.owner_cli.os.tcgetpgrp",
                return_value=os.getpgrp() + 1,
            ),
            self.assertRaisesRegex(ValueError, "foreground controlling terminal"),
        ):
            _read_owner_choice(card, rendered)


if __name__ == "__main__":
    unittest.main()
