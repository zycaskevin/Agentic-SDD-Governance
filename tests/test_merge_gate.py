import base64
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sddgov.merge_gate import change_digest, gate_metadata_digest, verify_merge


def _run(root: Path, *args: str) -> str:
    return subprocess.run(
        list(args), cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


class MergeGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        _run(self.root, "git", "init", "-q")
        _run(self.root, "git", "config", "user.email", "test@example.com")
        _run(self.root, "git", "config", "user.name", "Test Builder")
        (self.root / "core").mkdir()
        (self.root / "core/POLICY_KERNEL.md").write_text("baseline\n")
        (self.root / "policies").mkdir()
        (self.root / "policies/protected-files.yaml").write_text(
            "protected:\n  - core/POLICY_KERNEL.md\nrules:\n"
        )
        (self.root / ".sddgov").mkdir()
        self.reviewer_key = Ed25519PrivateKey.generate()
        public_key = self.reviewer_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        (self.root / ".sddgov/trusted-reviewers.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "reviewers": [{
                        "reviewer_id": "independent-reviewer",
                        "algorithm": "ed25519",
                        "public_key": base64.b64encode(public_key).decode("ascii"),
                        "status": "active",
                    }],
                }
            )
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
    types: [opened, synchronize, reopened, ready_for_review, converted_to_draft]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.event.pull_request.number || github.ref }}
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
            "# Rollback\n\n"
            "rollback_version: 1.0\n"
            "target: bounded test commit\n"
            "command: git revert HEAD\n"
            "verify: python -m unittest\n"
        )
        _run(self.root, "git", "add", ".")
        _run(self.root, "git", "commit", "-qm", "harden")

    def tearDown(self):
        self.temporary.cleanup()

    def _write_gate(
        self,
        review=True,
        *,
        reviewer_key=None,
        reviewer_id="independent-reviewer",
    ):
        digest = change_digest(self.root, self.base)
        gate = {
            "schema_version": "1.0",
            "base_sha": self.base,
            "head_sha": _run(self.root, "git", "rev-parse", "HEAD"),
            "risk_level": "L1",
            "builder_id": "codex-builder",
            "change_digest": digest,
            "deps": ["evidence/DEP-1"],
            "rollback_path": "evidence/DEP-1/rollback.md",
            "protected_file_review": None,
        }
        review_path = None
        if review:
            reviewer_key = reviewer_key or self.reviewer_key
            now = datetime.now(timezone.utc).replace(microsecond=0)
            review_payload = {
                "review_id": "REV-1",
                "reviewer_id": reviewer_id,
                "builder_id": "codex-builder",
                "change_digest": digest,
                "gate_metadata_digest": gate_metadata_digest(gate),
                "verdict": "approved",
                "issued_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                "nonce": "review-nonce-123456",
            }
            canonical = json.dumps(
                review_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            envelope = {
                "schema_version": "1.0",
                "algorithm": "ed25519",
                "review": review_payload,
                "signature": base64.b64encode(reviewer_key.sign(canonical)).decode("ascii"),
            }
            reviews = self.root / ".sddgov/reviews"
            reviews.mkdir(exist_ok=True)
            review_path = ".sddgov/reviews/REV-1.json"
            (self.root / review_path).write_text(json.dumps(envelope))
        gate["protected_file_review"] = review_path
        (self.root / ".sddgov/merge-gate.json").write_text(json.dumps(gate))
        if review:
            _run(self.root, "git", "add", ".sddgov/merge-gate.json", ".sddgov/reviews")
        else:
            _run(self.root, "git", "add", ".sddgov/merge-gate.json")
        _run(self.root, "git", "commit", "-qm", "merge receipt")

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_exact_change_green_dep_rollback_and_review_pass(self, _verify):
        self._write_gate()
        result = verify_merge(self.root, self.base)
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "MERGE_READY")
        self.assertEqual(result["protected_files_changed"], ["core/POLICY_KERNEL.md"])
        self.assertEqual(result["protected_file_reviewer"], "independent-reviewer")

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_protected_change_without_independent_review_fails(self, _verify):
        self._write_gate(review=False)
        with self.assertRaisesRegex(ValueError, "independent review"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_tracked_raw_evidence_fails(self, _verify):
        raw = self.root / "evidence/DEP-1/private/raw/leak.log"
        raw.parent.mkdir(parents=True)
        raw.write_text("secret")
        _run(self.root, "git", "add", "-f", str(raw.relative_to(self.root)))
        _run(self.root, "git", "commit", "-qm", "bad raw")
        self._write_gate()
        with self.assertRaisesRegex(ValueError, "raw evidence"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_deleted_raw_evidence_still_fails_history_scan(self, _verify):
        raw = self.root / "evidence/DEP-1/private/raw/deleted-leak.log"
        raw.parent.mkdir(parents=True)
        raw.write_text("secret")
        _run(self.root, "git", "add", "-f", str(raw.relative_to(self.root)))
        _run(self.root, "git", "commit", "-qm", "bad raw history")
        raw.unlink()
        _run(self.root, "git", "add", "-u")
        _run(self.root, "git", "commit", "-qm", "hide raw from head")
        self._write_gate()
        with self.assertRaisesRegex(ValueError, "raw evidence"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_review_binds_risk_and_dep_metadata(self, _verify):
        self._write_gate()
        gate_path = self.root / ".sddgov/merge-gate.json"
        gate = json.loads(gate_path.read_text())
        gate["risk_level"] = "L0"
        gate["deps"] = []
        gate_path.write_text(json.dumps(gate))
        _run(self.root, "git", "add", str(gate_path.relative_to(self.root)))
        _run(self.root, "git", "commit", "-qm", "tamper gate metadata")
        with self.assertRaisesRegex(ValueError, "exact executable change"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_gate_and_review_are_bound_to_exact_base_sha(self, _verify):
        self._write_gate()
        gate_path = self.root / ".sddgov/merge-gate.json"
        gate = json.loads(gate_path.read_text())
        gate["base_sha"] = "0" * 40
        gate_path.write_text(json.dumps(gate))
        _run(self.root, "git", "add", str(gate_path.relative_to(self.root)))
        _run(self.root, "git", "commit", "-qm", "tamper exact base")
        with self.assertRaisesRegex(ValueError, "base_sha"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_non_audit_descendant_after_reviewed_head_fails(self, _verify):
        self._write_gate()
        (self.root / "post-review.py").write_text("unsafe = True\n")
        _run(self.root, "git", "add", "post-review.py")
        _run(self.root, "git", "commit", "-qm", "change after review")
        with self.assertRaisesRegex(ValueError, "non-audit descendants"):
            verify_merge(self.root, self.base, run_checks=False)

    def test_dep_and_rollback_contents_are_inside_change_digest(self):
        before = change_digest(self.root, self.base)
        rollback = self.root / "evidence/DEP-1/rollback.md"
        rollback.write_text(rollback.read_text() + "verify: python -m unittest -v\n")
        _run(self.root, "git", "add", str(rollback.relative_to(self.root)))
        _run(self.root, "git", "commit", "-qm", "change rollback proof")
        self.assertNotEqual(before, change_digest(self.root, self.base))

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_candidate_policy_cannot_unprotect_base_paths(self, _verify):
        (self.root / "policies/protected-files.yaml").write_text(
            "protected:\n  - harmless.txt\nrules:\n"
        )
        _run(self.root, "git", "add", "policies/protected-files.yaml")
        _run(self.root, "git", "commit", "-qm", "attempt policy bypass")
        self._write_gate(review=False)
        with self.assertRaisesRegex(ValueError, "independent review"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_protected_source_path_cannot_be_renamed_out_of_policy(self, _verify):
        protected = self.root / "core/POLICY_KERNEL.md"
        protected.write_text("baseline\n")
        _run(self.root, "git", "add", "core/POLICY_KERNEL.md")
        _run(self.root, "git", "commit", "-qm", "restore rename source")
        _run(self.root, "git", "mv", "core/POLICY_KERNEL.md", "harmless.txt")
        _run(self.root, "git", "commit", "-qm", "attempt protected rename bypass")
        self._write_gate(review=False)
        with self.assertRaisesRegex(ValueError, "independent review"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_candidate_reviewer_key_cannot_authorize_change(self, _verify):
        rogue_key = Ed25519PrivateKey.generate()
        rogue_public = rogue_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        candidate_trust = {
            "schema_version": "1.0",
            "reviewers": [{
                "reviewer_id": "rogue-reviewer",
                "algorithm": "ed25519",
                "public_key": base64.b64encode(rogue_public).decode("ascii"),
                "status": "active",
            }],
        }
        (self.root / ".sddgov/trusted-reviewers.json").write_text(
            json.dumps(candidate_trust)
        )
        _run(self.root, "git", "add", ".sddgov/trusted-reviewers.json")
        _run(self.root, "git", "commit", "-qm", "attempt reviewer bypass")
        self._write_gate(reviewer_key=rogue_key, reviewer_id="rogue-reviewer")
        with self.assertRaisesRegex(ValueError, "not a unique active trusted reviewer"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_duplicate_reviewer_id_in_trusted_base_is_rejected(self, _verify):
        trust_path = self.root / ".sddgov/trusted-reviewers.json"
        trust = json.loads(trust_path.read_text())
        duplicate = dict(trust["reviewers"][0])
        duplicate["status"] = "revoked"
        trust["reviewers"].append(duplicate)
        trust_path.write_text(json.dumps(trust))
        _run(self.root, "git", "add", ".sddgov/trusted-reviewers.json")
        _run(self.root, "git", "commit", "-qm", "duplicate reviewer in base")
        self.base = _run(self.root, "git", "rev-parse", "HEAD")
        (self.root / "core/POLICY_KERNEL.md").write_text("hardened again\n")
        _run(self.root, "git", "add", "core/POLICY_KERNEL.md")
        _run(self.root, "git", "commit", "-qm", "protected follow-up")
        self._write_gate()
        with self.assertRaisesRegex(ValueError, "duplicate reviewer_id"):
            verify_merge(self.root, self.base, run_checks=False)

    @patch("sddgov.merge_gate.verify_dep", return_value=[])
    def test_arbitrary_rollback_prose_is_rejected(self, _verify):
        (self.root / "evidence/DEP-1/rollback.md").write_text("Rollback unavailable")
        _run(self.root, "git", "add", "evidence/DEP-1/rollback.md")
        _run(self.root, "git", "commit", "-qm", "invalid rollback")
        self._write_gate()
        with self.assertRaisesRegex(ValueError, "rollback record"):
            verify_merge(self.root, self.base, run_checks=False)


if __name__ == "__main__":
    unittest.main()
