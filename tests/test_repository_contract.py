import json
import unittest
from pathlib import Path

from sddgov.cli import _validate_repo


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_repository_assets_validate(self):
        self.assertEqual(_validate_repo(ROOT), [])

    def test_skill_is_thin_and_routes_one_level_references(self):
        skill = ROOT / "skill/agentic-sdd-governance/SKILL.md"
        lines = skill.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 150)
        text = "\n".join(lines)
        self.assertIn("references/evidence-workflow.md", text)
        self.assertNotIn("# Evidence-Driven SDD", text)

    def test_json_schemas_are_parseable(self):
        for path in (ROOT / "schemas").glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_adapters_route_to_canonical_skill(self):
        codex = (ROOT / "adapters/codex/AGENTS.md").read_text(encoding="utf-8")
        hermes = (ROOT / "adapters/hermes/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("agentic-sdd-governance", codex)
        self.assertIn("agentic-sdd-governance", hermes)
        self.assertIn("Red -> Evidence -> Fix -> Green -> Proof", codex)


if __name__ == "__main__":
    unittest.main()
