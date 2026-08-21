import hashlib
import io
import tarfile
import tempfile
import unittest
import zipfile
from os import environ
from pathlib import Path
from unittest.mock import patch

from scripts.fresh_wheel_smoke import (
    _regular_file,
    _snapshot_verified_bundle,
    verify_offline_bundle,
)
from scripts.prepare_release_bundle import prepare_release_bundle


class ReleaseBundleTests(unittest.TestCase):
    @staticmethod
    def _metadata(name: str, version: str) -> bytes:
        return (
            "Metadata-Version: 2.4\n"
            f"Name: {name}\n"
            f"Version: {version}\n\n"
        ).encode("utf-8")

    def _write_wheel(self, path: Path, name: str, version: str) -> None:
        dist_info = f"{name.replace('-', '_')}-{version}.dist-info"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                f"{dist_info}/METADATA",
                self._metadata(name, version),
            )
            archive.writestr(f"{name.replace('-', '_')}/__init__.py", b"")

    def _write_sdist(self, path: Path, name: str, version: str) -> None:
        metadata = self._metadata(name, version)
        member = tarfile.TarInfo(f"{name}-{version}/PKG-INFO")
        member.size = len(metadata)
        member.mode = 0o644
        with tarfile.open(path, "w:gz") as archive:
            archive.addfile(member, io.BytesIO(metadata))

    def _fixture(self, root: Path):
        dist = root / "dist"
        wheelhouse = root / "wheelhouse"
        output = root / "release"
        dist.mkdir()
        wheelhouse.mkdir()
        wheel = dist / "agentic_sdd_governance-0.2.0rc1-py3-none-any.whl"
        self._write_wheel(wheel, "agentic-sdd-governance", "0.2.0rc1")
        source_archive = dist / "agentic_sdd_governance-0.2.0rc1.tar.gz"
        self._write_sdist(
            source_archive,
            "agentic-sdd-governance",
            "0.2.0rc1",
        )
        dependency = wheelhouse / "dependency-1.0-py3-none-any.whl"
        self._write_wheel(dependency, "dependency", "1.0")
        dependency_digest = hashlib.sha256(dependency.read_bytes()).hexdigest()
        lock = root / "requirements-governance.lock"
        lock.write_text(
            "dependency==1.0 \\\n"
            f"    --hash=sha256:{dependency_digest}\n",
            encoding="utf-8",
        )
        return dist, wheelhouse, output, wheel, source_archive, dependency, lock

    def _prepare(self, root: Path):
        dist, wheelhouse, output, wheel, _source, _dependency, lock = self._fixture(
            root
        )
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

    def test_dependency_hash_mismatch_fails_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dist, wheelhouse, output, _wheel, _source, _dependency, lock = (
                self._fixture(root)
            )
            lock.write_text(
                "dependency==1.0 --hash=sha256:" + "a" * 64 + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "locked hash"):
                prepare_release_bundle(
                    dist,
                    wheelhouse,
                    lock,
                    output,
                    "0.2.0rc1",
                    "linux-x86_64-py312",
                )
            self.assertFalse(output.exists())

    def test_project_wheel_and_sdist_versions_must_match_release(self):
        for artifact in ("wheel", "sdist"):
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                dist, wheelhouse, output, wheel, source, _dependency, lock = (
                    self._fixture(root)
                )
                if artifact == "wheel":
                    self._write_wheel(wheel, "agentic-sdd-governance", "9.9")
                else:
                    self._write_sdist(source, "agentic-sdd-governance", "9.9")
                with self.assertRaisesRegex(ValueError, "version"):
                    prepare_release_bundle(
                        dist,
                        wheelhouse,
                        lock,
                        output,
                        "0.2.0rc1",
                        "linux-x86_64-py312",
                    )
                self.assertFalse(output.exists())

    def test_verified_private_snapshot_is_immutable_install_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheel, output, _report = self._prepare(root)
            verified = verify_offline_bundle(output / "offline", wheel)
            snapshot = _snapshot_verified_bundle(
                verified,
                wheel,
                root / "private-snapshot",
            )
            snapshot_wheel = snapshot["wheel"].read_bytes()
            snapshot_lock = snapshot["lock"].read_bytes()
            snapshot_dependencies = {
                path.name: path.read_bytes()
                for path in snapshot["wheelhouse"].iterdir()
            }

            wheel.write_bytes(b"replaced after snapshot")
            (output / "offline/requirements-governance.lock").write_bytes(
                b"replaced after snapshot"
            )
            next((output / "offline/wheelhouse").iterdir()).write_bytes(
                b"replaced after snapshot"
            )

            self.assertEqual(snapshot["wheel"].read_bytes(), snapshot_wheel)
            self.assertEqual(snapshot["lock"].read_bytes(), snapshot_lock)
            self.assertEqual(
                {
                    path.name: path.read_bytes()
                    for path in snapshot["wheelhouse"].iterdir()
                },
                snapshot_dependencies,
            )
            self.assertTrue(snapshot["root"].is_relative_to(root / "private-snapshot"))

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
