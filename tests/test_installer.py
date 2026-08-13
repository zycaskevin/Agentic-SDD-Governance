import json
import tempfile
import unittest
from pathlib import Path

from sddgov.installer import (
    END_MARKER,
    START_MARKER,
    _resource_files,
    doctor,
    setup_agent,
    uninstall_agent,
)
from sddgov.governance import init_project


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_codex_setup_is_discoverable_idempotent_and_preserves_agents(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            agents = project / "AGENTS.md"
            agents.write_text("# Existing Project Rules\n\nKeep this text.\n", encoding="utf-8")
            gitignore = project / ".gitignore"
            gitignore.write_text("build/\n", encoding="utf-8")

            result = setup_agent(project, "codex", "team-standard")
            self.assertEqual(result["status"], "installed")
            text = agents.read_text(encoding="utf-8")
            self.assertIn("# Existing Project Rules", text)
            self.assertIn(START_MARKER, text)
            self.assertIn(END_MARKER, text)
            self.assertTrue(
                (project / ".agents/skills/agentic-sdd-governance/SKILL.md").is_file()
            )
            self.assertTrue(
                (project / ".agentic-sdd-governance/core/POLICY_KERNEL.md").is_file()
            )
            self.assertTrue(
                (
                    project
                    / ".agentic-sdd-governance/templates/CI_COST_GUARD.json"
                ).is_file()
            )
            self.assertTrue(doctor(project)["ok"])
            self.assertIn("build/", gitignore.read_text(encoding="utf-8"))
            self.assertIn(
                "evidence/**/private/raw/", gitignore.read_text(encoding="utf-8")
            )
            self.assertIn(".sddgov/*.lock", gitignore.read_text(encoding="utf-8"))

            repeated = setup_agent(project, "codex", "team-standard")
            self.assertEqual(repeated["status"], "already-installed")
            self.assertEqual(agents.read_text(encoding="utf-8").count(START_MARKER), 1)

    def test_hermes_setup_and_forced_profile_switch(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            setup_agent(project, "codex", "team-standard")
            updated = setup_agent(project, "hermes", "solo-fast", force=True)
            self.assertEqual(updated["status"], "updated")
            report = doctor(project)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["agent"], "hermes")
            self.assertEqual(report["profile"], "solo-fast")
            self.assertIn("Hermes Agent", (project / "AGENTS.md").read_text(encoding="utf-8"))
            state = json.loads((project / ".sddgov/project.json").read_text(encoding="utf-8"))
            self.assertEqual(state["profile"], "solo-fast")

    def test_doctor_detects_tampering_and_uninstall_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            setup_agent(project, "codex", "team-standard")
            skill = project / ".agents/skills/agentic-sdd-governance/SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")
            gitignore = project / ".gitignore"
            gitignore.write_text(
                gitignore.read_text(encoding="utf-8").replace(
                    "evidence/**/private/raw/", "evidence/**/private/not-raw/"
                ),
                encoding="utf-8",
            )

            report = doctor(project)
            self.assertFalse(report["ok"])
            self.assertTrue(any("modified managed file" in item for item in report["errors"]))
            self.assertIn(".gitignore raw-evidence block was modified", report["errors"])
            with self.assertRaises(ValueError):
                uninstall_agent(project)

            result = uninstall_agent(project, force=True)
            self.assertEqual(result["status"], "uninstalled")
            self.assertTrue((project / ".sddgov/project.json").is_file())

    def test_uninstall_removes_only_managed_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            agents = project / "AGENTS.md"
            agents.write_text("# Existing Project Rules\n", encoding="utf-8")
            gitignore = project / ".gitignore"
            gitignore.write_text("dist/\n", encoding="utf-8")
            evidence = project / "evidence/DEP-KEEP/manifest.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("{}\n", encoding="utf-8")
            setup_agent(project, "codex", "team-standard")

            result = uninstall_agent(project)
            self.assertEqual(result["retained"], [".sddgov", "evidence/*/shareable"])
            self.assertEqual(agents.read_text(encoding="utf-8"), "# Existing Project Rules\n")
            self.assertEqual(gitignore.read_text(encoding="utf-8"), "dist/\n")
            self.assertTrue(evidence.is_file())
            self.assertFalse((project / ".agentic-sdd-governance").exists())
            self.assertFalse((project / ".agents").exists())

    def test_install_manifest_does_not_claim_raw_evidence_retention(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            setup_agent(project, "codex", "team-standard")
            manifest = json.loads(
                (project / ".agentic-sdd-governance/manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(manifest["uninstall_retains"], [".sddgov", "evidence/*/shareable"])
            cleanup = manifest["uninstall_local_cleanup_required"]
            self.assertEqual(cleanup["path"], "evidence/*/private/raw")
            self.assertIn("repository owner", cleanup["owner"])
            self.assertIn("repository retention policy", cleanup["retention"])

    def test_doctor_requires_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = doctor(Path(temporary))
            self.assertFalse(report["ok"])
            self.assertIn("setup-agent", report["errors"][0])

    def test_setup_does_not_silently_change_existing_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, "regulated")
            with self.assertRaises(ValueError):
                setup_agent(project, "codex", "team-standard")
            setup_agent(project, "codex", "team-standard", force=True)
            self.assertTrue(doctor(project)["ok"])

    def test_forced_same_version_setup_refreshes_managed_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            setup_agent(project, "codex", "team-standard")

            refreshed = setup_agent(project, "codex", "team-standard", force=True)

            self.assertEqual(refreshed["status"], "updated")
            self.assertTrue(doctor(project)["ok"])

    def test_setup_does_not_replace_unmanaged_gitignore_block(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            gitignore = project / ".gitignore"
            gitignore.write_text(
                "# agentic-sdd-governance:start\n"
                "evidence/custom/private/\n"
                "# agentic-sdd-governance:end\n",
                encoding="utf-8",
            )

            with self.assertRaises(FileExistsError):
                setup_agent(project, "codex", "team-standard")
            self.assertIn("evidence/custom/private/", gitignore.read_text(encoding="utf-8"))

            setup_agent(project, "codex", "team-standard", force=True)
            self.assertTrue(doctor(project)["ok"])
            self.assertIn("evidence/**/private/raw/", gitignore.read_text(encoding="utf-8"))

    def test_doctor_detects_manifest_omission(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            setup_agent(project, "codex", "team-standard")
            manifest_path = project / ".agentic-sdd-governance/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["managed_files"].pop(
                ".agents/skills/agentic-sdd-governance/SKILL.md"
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = doctor(project)
            self.assertFalse(report["ok"])
            self.assertTrue(any("omitted managed file" in item for item in report["errors"]))

    def test_forced_upgrade_does_not_emit_a_second_initialization_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            setup_agent(project, "codex", "team-standard")
            managed = project / ".agentic-sdd-governance/VERSION"
            managed.write_text("tampered\n", encoding="utf-8")

            setup_agent(project, "codex", "team-standard", force=True)

            events = [
                json.loads(line)
                for line in (project / ".sddgov/events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            initialized = [event for event in events if event["event_type"] == "governance_initialized"]
            self.assertEqual(len(initialized), 1)

    def test_version_upgrade_emits_a_version_specific_audit_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            setup_agent(project, "codex", "team-standard")
            state_path = project / ".sddgov/project.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["governance_version"] = "0.2.0-experimental.3"
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

            setup_agent(project, "codex", "team-standard", force=True)

            events = [
                json.loads(line)
                for line in (project / ".sddgov/events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(events[-1]["event_type"], "governance_version_updated")
            self.assertEqual(
                events[-1]["payload"]["previous_governance_version"],
                "0.2.0-experimental.3",
            )
            self.assertEqual(events[-1]["payload"]["governance_version"], "0.2.0-experimental.5")

    def test_packaged_install_assets_match_canonical_sources(self):
        for relative, content in _resource_files().items():
            canonical = ROOT / relative
            self.assertTrue(canonical.is_file(), relative)
            self.assertEqual(content, canonical.read_bytes(), relative)


if __name__ == "__main__":
    unittest.main()
