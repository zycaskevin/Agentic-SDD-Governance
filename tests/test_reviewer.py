import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sddgov.merge_gate import change_digest, gate_metadata_digest, verify_merge
from sddgov.reviewer import bootstrap_reviewer, sign_protected_review


def _run(root: Path, *args: str) -> str:
    return subprocess.run(
        list(args), cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


class ReviewerBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        self.external = Path(self.temporary.name) / "reviewer-control"
        self.root.mkdir()
        self.external.mkdir(mode=0o700)

    def tearDown(self):
        self.temporary.cleanup()

    def test_bootstrap_creates_owner_only_external_identity_without_printing_private_key(self):
        key_path = self.external / "reviewer.pem"
        trust_path = self.external / "trusted-reviewers.json"
        result = bootstrap_reviewer(
            self.root,
            reviewer_id="gb10-hermes-reviewer",
            private_key_path=key_path,
            trust_path=trust_path,
        )

        self.assertTrue(result["ok"])
        self.assertNotIn("private_key", result)
        self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(trust_path.stat().st_mode & 0o777, 0o600)
        trust = json.loads(trust_path.read_text())
        self.assertEqual(trust["reviewers"][0]["reviewer_id"], "gb10-hermes-reviewer")
        self.assertEqual(len(base64.b64decode(trust["reviewers"][0]["public_key"])), 32)
        self.assertEqual(json.loads(result["github_variable_value"]), trust)

    def test_bootstrap_rejects_repo_local_key_or_trust_store(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            bootstrap_reviewer(
                self.root,
                reviewer_id="reviewer",
                private_key_path=self.root / "reviewer.pem",
                trust_path=self.external / "trust.json",
            )
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            bootstrap_reviewer(
                self.root,
                reviewer_id="reviewer",
                private_key_path=self.external / "reviewer.pem",
                trust_path=self.root / "trust.json",
            )

    def test_bootstrap_never_overwrites_existing_identity(self):
        key_path = self.external / "reviewer.pem"
        trust_path = self.external / "trusted-reviewers.json"
        bootstrap_reviewer(self.root, "reviewer", key_path, trust_path)
        with self.assertRaises(FileExistsError):
            bootstrap_reviewer(self.root, "reviewer", key_path, trust_path)


class ReviewerSigningTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        self.external = Path(self.temporary.name) / "reviewer-control"
        self.root.mkdir()
        self.external.mkdir(mode=0o700)
        _run(self.root, "git", "init", "-q")
        _run(self.root, "git", "config", "user.email", "reviewer-test@example.com")
        _run(self.root, "git", "config", "user.name", "Reviewer Test")
        (self.root / "core").mkdir()
        (self.root / "core/POLICY_KERNEL.md").write_text("baseline\n")
        (self.root / "policies").mkdir()
        (self.root / "policies/protected-files.yaml").write_text(
            "protected:\n  - core/POLICY_KERNEL.md\nrules:\n"
        )
        (self.root / ".sddgov").mkdir()
        (self.root / ".sddgov/trusted-reviewers.json").write_text(
            json.dumps({"schema_version": "1.0", "reviewers": []})
        )
        (self.root / ".sddgov/ci-cost-guard.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "profile": "team-standard",
                    "local_green": {
                        "environment": {},
                        "commands": [[sys.executable, "-c", "pass"]],
                    },
                    "hosted": {
                        "max_runs_per_work_package": 1,
                        "max_reruns_per_revision": 1,
                        "expected_minutes": 5,
                        "full_matrix": "manual_or_ready_for_review",
                    },
                    "workflow_controls": {
                        "require_concurrency": True,
                        "cancel_in_progress": True,
                        "require_job_timeouts": True,
                        "require_read_only_permissions": True,
                        "skip_draft_pull_requests": True,
                        "exempt_workflows": [],
                    },
                }
            )
        )
        workflows = self.root / ".github/workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text(
            """name: CI
on:
  pull_request:
permissions:
  contents: read
concurrency:
  group: ci
  cancel-in-progress: true
jobs:
  verify:
    if: github.event_name != 'pull_request' || github.event.pull_request.draft == false
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: true
"""
        )
        _run(self.root, "git", "add", ".")
        _run(self.root, "git", "commit", "-qm", "baseline")
        self.base = _run(self.root, "git", "rev-parse", "HEAD")
        (self.root / "core/POLICY_KERNEL.md").write_text("hardened\n")
        rollback = self.root / "evidence/DEP-1/rollback.md"
        rollback.parent.mkdir(parents=True)
        rollback.write_text(
            "rollback_version: 2.0\n"
            "target: bounded reviewer test\n"
            "rollback_action: git_revert\n"
            "rollback_ref: HEAD\n"
            "verify_action: python_module\n"
            "verify_module: unittest\n"
        )
        _run(self.root, "git", "add", ".")
        _run(self.root, "git", "commit", "-qm", "harden")
        self.reviewed_head = _run(self.root, "git", "rev-parse", "HEAD")
        self.key_path = self.external / "reviewer.pem"
        self.trust_path = self.external / "trusted-reviewers.json"
        bootstrap_reviewer(
            self.root,
            "gb10-hermes-reviewer",
            self.key_path,
            self.trust_path,
        )
        self.receipt = self.root / ".sddgov/reviews/REV-1.json"
        gate = {
            "schema_version": "1.0",
            "base_sha": self.base,
            "head_sha": self.reviewed_head,
            "risk_level": "L1",
            "builder_id": "codex-builder",
            "change_digest": change_digest(self.root, self.base),
            "deps": ["evidence/DEP-1"],
            "rollback_path": "evidence/DEP-1/rollback.md",
            "protected_file_review": ".sddgov/reviews/REV-1.json",
        }
        (self.root / ".sddgov/merge-gate.json").write_text(json.dumps(gate))
        _run(self.root, "git", "add", ".sddgov/merge-gate.json")
        _run(self.root, "git", "commit", "-qm", "bind merge gate")

    def tearDown(self):
        self.temporary.cleanup()

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_sign_creates_exact_receipt_that_merge_gate_accepts(self, _verify):
        result = sign_protected_review(
            self.root,
            reviewer_id="gb10-hermes-reviewer",
            private_key_path=self.key_path,
            trust_path=self.trust_path,
            review_id="REV-1",
            output_path=self.receipt,
            base_ref=self.base,
            approved=True,
        )
        self.assertTrue(result["ok"])
        self.assertNotIn("signature", result)
        _run(self.root, "git", "add", ".sddgov/reviews/REV-1.json")
        _run(self.root, "git", "commit", "-qm", "independent review receipt")
        with patch.dict(
            os.environ, {"SDDGOV_TRUSTED_REVIEWERS_FILE": str(self.trust_path)}
        ):
            verified = verify_merge(self.root, self.base, run_checks=False)
        self.assertTrue(verified["ok"])
        self.assertEqual(verified["protected_file_reviewer"], "gb10-hermes-reviewer")

    def test_sign_rejects_dirty_or_untracked_review_workspace(self):
        (self.root / "leftover.tmp").write_text("untracked")
        with self.assertRaisesRegex(ValueError, "clean exact-HEAD"):
            sign_protected_review(
                self.root,
                "gb10-hermes-reviewer",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                base_ref=self.base,
                approved=True,
            )

    def test_sign_rejects_builder_as_reviewer(self):
        with self.assertRaisesRegex(ValueError, "independent"):
            sign_protected_review(
                self.root,
                "codex-builder",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                base_ref=self.base,
                approved=True,
            )

    def test_sign_rejects_private_key_with_broad_permissions(self):
        self.key_path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            sign_protected_review(
                self.root,
                "gb10-hermes-reviewer",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                base_ref=self.base,
                approved=True,
            )

    def test_sign_rejects_key_not_registered_in_trust_store(self):
        other_key = Ed25519PrivateKey.generate()
        self.key_path.write_bytes(
            other_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        self.key_path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "does not match"):
            sign_protected_review(
                self.root,
                "gb10-hermes-reviewer",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                base_ref=self.base,
                approved=True,
            )

    def test_sign_requires_explicit_approved_verdict(self):
        with self.assertRaisesRegex(ValueError, "explicit approved verdict"):
            sign_protected_review(
                self.root,
                "gb10-hermes-reviewer",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                base_ref=self.base,
            )

    def test_sign_requires_independently_selected_base_ref(self):
        with self.assertRaisesRegex(ValueError, "base_ref is required"):
            sign_protected_review(
                self.root,
                "gb10-hermes-reviewer",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                approved=True,
            )

    @patch(
        "sddgov.reviewer.serialization.load_pem_private_key",
        side_effect=UnsupportedAlgorithm("unsupported"),
    )
    def test_sign_normalizes_unsupported_private_key_algorithm(self, _load):
        with self.assertRaisesRegex(ValueError, "valid unencrypted PEM"):
            sign_protected_review(
                self.root,
                "gb10-hermes-reviewer",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                base_ref=self.base,
                approved=True,
            )

    def test_sign_rejects_broadly_writable_trust_store(self):
        self.trust_path.chmod(0o666)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            sign_protected_review(
                self.root,
                "gb10-hermes-reviewer",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                base_ref=self.base,
                approved=True,
            )

    def test_sign_rejects_merge_gate_outside_repository(self):
        outside_gate = self.external / "merge-gate.json"
        outside_gate.write_text((self.root / ".sddgov/merge-gate.json").read_text())
        outside_gate.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            sign_protected_review(
                self.root,
                "gb10-hermes-reviewer",
                self.key_path,
                self.trust_path,
                "REV-1",
                self.receipt,
                base_ref=self.base,
                gate_path=outside_gate,
                approved=True,
            )


if __name__ == "__main__":
    unittest.main()
