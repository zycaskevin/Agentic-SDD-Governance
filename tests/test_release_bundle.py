import tempfile
import unittest
from os import environ
from pathlib import Path
from unittest.mock import patch

from scripts.fresh_wheel_smoke import _regular_file, verify_offline_bundle
from scripts.prepare_release_bundle import prepare_release_bundle


class ReleaseBundleTests(unittest.TestCase):
    def _prepare(self, root: Path):
        dist = root / "dist"
        wheelhouse = root / "wheelhouse"
        output = root / "release"
        dist.mkdir()
        wheelhouse.mkdir()
        wheel = dist / "agentic_sdd_governance-0.2.0rc1-py3-none-any.whl"
        wheel.write_bytes(b"synthetic-project-wheel")
        (dist / "agentic_sdd_governance-0.2.0rc1.tar.gz").write_bytes(
            b"synthetic-source-archive"
        )
        (wheelhouse / "dependency-1.0-py3-none-any.whl").write_bytes(
            b"synthetic-dependency-wheel"
        )
        lock = root / "requirements-governance.lock"
        lock.write_text("dependency==1.0 --hash=sha256:" + "a" * 64 + "\n")
        report = prepare_release_bundle(
            dist,
            wheelhouse,
            lock,
            output,
            "0.2.0rc1",
            "linux-x86_64-py312",
        )
        return wheel, output, report

    def test_bundle_has_locked_dependencies_and_exact_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            wheel, output, report = self._prepare(Path(temporary))
            verified = verify_offline_bundle(output / "offline", wheel)
            self.assertTrue(report["ok"])
            self.assertEqual(report["dependency_wheel_count"], 1)
            self.assertEqual(verified["file_count"], 3)
            self.assertTrue((output / report["offline_archive"]).is_file())

    def test_unlisted_bundle_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            wheel, output, _report = self._prepare(Path(temporary))
            (output / "offline/unlisted.txt").write_text("not inventoried\n")
            with self.assertRaisesRegex(ValueError, "does not exactly match"):
                verify_offline_bundle(output / "offline", wheel)

    def test_bundle_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            wheel, output, _report = self._prepare(Path(temporary))
            dependency = next((output / "offline/wheelhouse").glob("*.whl"))
            dependency.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "bundle digest mismatch"):
                verify_offline_bundle(output / "offline", wheel)

    def test_symlinked_bundle_root_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheel, output, _report = self._prepare(root)
            linked = root / "linked-offline"
            linked.symlink_to(output / "offline", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "non-symlink directory"):
                verify_offline_bundle(linked, wheel)

    def test_regular_file_validation_expands_the_user_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            wheel = home / "synthetic.whl"
            wheel.write_bytes(b"synthetic")
            with patch.dict(environ, {"HOME": str(home)}):
                self.assertEqual(
                    _regular_file(Path("~/synthetic.whl"), "wheel"),
                    wheel.resolve(),
                )


if __name__ == "__main__":
    unittest.main()
