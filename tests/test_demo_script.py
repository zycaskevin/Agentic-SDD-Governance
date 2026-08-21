import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoScriptTests(unittest.TestCase):
    def _demo_fixture(self, root: Path, cli_source: str) -> Path:
        demo_dir = root / "demo"
        cli_dir = root / ".venv/bin"
        demo_dir.mkdir(parents=True)
        cli_dir.mkdir(parents=True)
        demo = demo_dir / "run.sh"
        shutil.copy2(ROOT / "demo/run.sh", demo)
        cli = cli_dir / "sddgov"
        cli.write_text(cli_source, encoding="utf-8")
        cli.chmod(0o755)
        return demo

    def test_failed_pilot_result_is_rendered_before_demo_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            demo = self._demo_fixture(
                Path(temporary),
                """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

Path(sys.argv[-1]).write_text(json.dumps({
    "routine_l1_continues": True,
    "dangerous_downgrade_blocked": True,
    "text_redaction_ok": True,
    "binary_evidence_fail_closed": False,
    "agent_install_ok": True,
    "strict_dep_ok": True,
    "verdict": "FAIL",
}) + "\\n", encoding="utf-8")
raise SystemExit(1)
""",
            )
            completed = subprocess.run(
                [str(demo)],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "TMPDIR": temporary},
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("Verdict: FAIL", completed.stdout)
        self.assertIn("[FAIL] Binary Evidence", completed.stdout)

    def test_pilot_failure_without_result_fails_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            demo = self._demo_fixture(
                Path(temporary),
                "#!/usr/bin/env bash\nexit 7\n",
            )
            completed = subprocess.run(
                [str(demo)],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "TMPDIR": temporary},
            )
        self.assertEqual(completed.returncode, 7)
        self.assertIn("failed before producing a result", completed.stderr)

    def test_nonzero_pilot_status_cannot_be_masked_by_a_pass_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            demo = self._demo_fixture(
                Path(temporary),
                """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

Path(sys.argv[-1]).write_text(json.dumps({
    "routine_l1_continues": True,
    "dangerous_downgrade_blocked": True,
    "text_redaction_ok": True,
    "binary_evidence_fail_closed": True,
    "agent_install_ok": True,
    "strict_dep_ok": True,
    "verdict": "PASS",
}) + "\\n", encoding="utf-8")
raise SystemExit(7)
""",
            )
            completed = subprocess.run(
                [str(demo)],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "TMPDIR": temporary},
            )
        self.assertEqual(completed.returncode, 7)
        self.assertIn("Verdict: PASS", completed.stdout)


if __name__ == "__main__":
    unittest.main()
