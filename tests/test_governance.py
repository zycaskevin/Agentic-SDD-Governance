import json
import tempfile
import unittest
from pathlib import Path

from sddgov.governance import claim_work, enqueue_external_action, init_project, project_status


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_init_claim_status_and_external_queue(self):
        created = init_project(self.root, "team-standard")
        self.assertTrue(created)
        claim = claim_work(self.root, "WP-001", "builder-1", ttl_minutes=30)
        self.assertEqual(claim["status"], "active")
        with self.assertRaisesRegex(ValueError, "already has an active claim"):
            claim_work(self.root, "WP-001", "builder-2", ttl_minutes=30)
        action = enqueue_external_action(self.root, "OA-001", "Owner completes MFA", "L3", "product-owner")
        self.assertEqual(action["authorization_scope"], "one concrete action only")
        status = project_status(self.root)
        self.assertEqual(status["active_claims"], 1)
        self.assertEqual(status["pending_external_actions"], 1)
        self.assertGreaterEqual(status["event_count"], 3)

    def test_external_action_rejects_routine_engineering(self):
        init_project(self.root, "solo-fast")
        with self.assertRaisesRegex(ValueError, "must be L2 or L3"):
            enqueue_external_action(self.root, "OA-LOW", "Run unit test", "L1", "agent")

    def test_event_log_is_jsonl(self):
        init_project(self.root, "regulated")
        lines = (self.root / ".sddgov/events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertTrue(lines)
        self.assertEqual(json.loads(lines[0])["event_type"], "governance_initialized")


if __name__ == "__main__":
    unittest.main()
