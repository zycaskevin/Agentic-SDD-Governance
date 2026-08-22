import hashlib
import io
import json
import stat
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from os import environ
from pathlib import Path
from unittest.mock import patch

from sddgov import __version__ as RELEASE_VERSION

from scripts.fresh_wheel_smoke import (
    _public_error as smoke_public_error,
    _run,
    _snapshot_verified_bundle,
    main as smoke_main,
    verify_offline_bundle,
)
from scripts.prepare_release_bundle import main as prepare_main
from scripts.prepare_release_bundle import _public_error as bundle_public_error
from scripts.prepare_release_bundle import prepare_release_bundle
from scripts.release_files import open_directory, open_regular_file


class ReleaseBundleTests(unittest.TestCase):
    def test_shareable_failure_reports_mask_local_paths(self):
        local = Path(tempfile.gettempdir()) / "sddgov-sensitive-build/input.whl"
        for sanitizer in (smoke_public_error, bundle_public_error):
            with self.subTest(sanitizer=sanitizer.__module__):
                rendered = sanitizer(f"failed to read {local}: denied")
                self.assertNotIn(str(local), rendered)
                self.assertIn("<local-path>", rendered)

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
        wheel = dist / f"agentic_sdd_governance-{RELEASE_VERSION}-py3-none-any.whl"
        self._write_wheel(wheel, "agentic-sdd-governance", RELEASE_VERSION)
        source_archive = dist / f"agentic_sdd_governance-{RELEASE_VERSION}.tar.gz"
        self._write_sdist(
            source_archive,
            "agentic-sdd-governance",
            RELEASE_VERSION,
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
            RELEASE_VERSION,
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
            self.assertEqual(verified["bundle_file_count"], 4)
            self.assertTrue((output / report["offline_archive"]).is_file())
            names = [
                row.split("  ", 1)[1]
                for row in (output / "SHA256SUMS.txt")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(names, sorted(names))

    def test_fresh_wheel_command_timeout_is_configurable(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.fresh_wheel_smoke.subprocess.run"
        ) as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "ok\n"
            run.return_value.stderr = ""
            result = _run(
                ["synthetic-command"],
                cwd=Path(temporary),
                environment={},
                timeout=321,
            )
        self.assertEqual(result, "ok")
        self.assertEqual(run.call_args.kwargs["timeout"], 321)

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

    def test_nested_dependency_wheel_path_fails_with_precise_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheel, output, _report = self._prepare(root)
            offline = output / "offline"
            dependency = next((offline / "wheelhouse").glob("*.whl"))
            nested = offline / "wheelhouse/nested"
            nested.mkdir()
            nested_dependency = nested / dependency.name
            dependency.rename(nested_dependency)
            manifest = offline / "SHA256SUMS.txt"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    f"wheelhouse/{dependency.name}",
                    f"wheelhouse/nested/{dependency.name}",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "direct children"):
                verify_offline_bundle(offline, wheel)

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
                    RELEASE_VERSION,
                    "linux-x86_64-py312",
                )
            self.assertFalse(output.exists())

    def test_project_wheel_and_sdist_versions_must_match_release(self):
        expected_errors = {
            "wheel": "project wheel filename and metadata name/version do not match",
            "sdist": "source archive filename and metadata name/version do not match",
        }
        for artifact, expected_error in expected_errors.items():
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                dist, wheelhouse, output, wheel, source, _dependency, lock = (
                    self._fixture(root)
                )
                if artifact == "wheel":
                    self._write_wheel(wheel, "agentic-sdd-governance", "9.9")
                else:
                    self._write_sdist(source, "agentic-sdd-governance", "9.9")
                with self.assertRaisesRegex(
                    ValueError,
                    expected_error,
                ):
                    prepare_release_bundle(
                        dist,
                        wheelhouse,
                        lock,
                        output,
                        RELEASE_VERSION,
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
            self.assertEqual(snapshot["root"], root / "private-snapshot")
            self.assertEqual(stat.S_IMODE(snapshot["root"].stat().st_mode), 0o700)
            self.assertEqual(
                stat.S_IMODE(snapshot["wheelhouse"].stat().st_mode), 0o700
            )
            self.assertEqual(
                snapshot["bundle_file_count"], verified["bundle_file_count"]
            )

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
                with open_regular_file(
                    Path("~/synthetic.whl"), "wheel"
                ) as opened:
                    self.assertEqual(opened.path, wheel.resolve())

    def test_open_release_input_fails_closed_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "artifact.whl"
            displaced = root / "displaced.whl"
            source.write_bytes(b"reviewed release bytes")

            with open_regular_file(source, "release artifact") as opened:
                source.rename(displaced)
                source.write_bytes(b"attacker replacement")

                with self.assertRaisesRegex(ValueError, "changed after it was opened"):
                    opened.read_bytes()
                self.assertNotEqual(
                    hashlib.sha256(b"reviewed release bytes").hexdigest(),
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                )

    def test_open_release_input_detects_in_place_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "artifact.whl"
            source.write_bytes(b"reviewed release bytes")

            with open_regular_file(source, "release artifact") as opened:
                source.write_bytes(b"mutated release bytes")
                with self.assertRaisesRegex(ValueError, "changed after it was opened"):
                    opened.read_bytes()

    def test_open_directory_retains_input_and_output_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            redirected_source = root / "redirected-source"
            source.mkdir()
            redirected_source.mkdir()
            (source / "artifact.whl").write_bytes(b"reviewed")
            (redirected_source / "artifact.whl").write_bytes(b"redirected")
            with open_directory(source, "source directory") as opened_source:
                source.rename(root / "source-original")
                source.symlink_to(redirected_source, target_is_directory=True)
                with opened_source.open_regular_file(
                    "artifact.whl", "artifact"
                ) as artifact:
                    self.assertEqual(artifact.read_bytes(), b"reviewed")

            output = root / "output"
            redirected_output = root / "redirected-output"
            redirected_output.mkdir()
            with open_directory(
                output, "output directory", create=True
            ) as opened_output:
                output.rename(root / "output-original")
                output.symlink_to(redirected_output, target_is_directory=True)
                opened_output.write_bytes("result.txt", b"trusted\n")
            self.assertEqual(
                (root / "output-original/result.txt").read_bytes(), b"trusted\n"
            )
            self.assertFalse((redirected_output / "result.txt").exists())

    def test_release_helpers_fail_clearly_on_non_posix_hosts(self):
        with patch("scripts.release_files.os.name", "nt"), self.assertRaisesRegex(
            ValueError, "require Linux or macOS"
        ):
            open_directory(Path("C:/synthetic/release"), "release directory")

    def test_open_directory_create_only_creates_the_final_component(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing_parent = Path(temporary) / "missing" / "output"
            with self.assertRaises(FileNotFoundError):
                open_directory(missing_parent, "release directory", create=True)

    def test_release_cleanup_preserves_the_primary_failure(self):
        cases = ("write_bytes", "write_from_descriptor", "binary_writer")
        for operation in cases:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with open_directory(root, "release directory") as output, patch.object(
                    output,
                    "_remove_owned",
                    side_effect=ValueError("synthetic cleanup failure"),
                ):
                    if operation == "write_bytes":
                        with patch(
                            "scripts.release_files.os.write",
                            side_effect=OSError("synthetic primary failure"),
                        ), self.assertRaisesRegex(
                            OSError, "synthetic primary failure"
                        ) as raised:
                            output.write_bytes("result.bin", b"value")
                    elif operation == "write_from_descriptor":
                        with tempfile.TemporaryFile() as source, patch(
                            "scripts.release_files.os.write",
                            side_effect=OSError("synthetic primary failure"),
                        ), self.assertRaisesRegex(
                            OSError, "synthetic primary failure"
                        ) as raised:
                            source.write(b"value")
                            source.seek(0)
                            output.write_from_descriptor(
                                "result.bin", source.fileno()
                            )
                    else:
                        with self.assertRaisesRegex(
                            RuntimeError, "synthetic primary failure"
                        ) as raised:
                            with output.binary_writer("result.bin"):
                                raise RuntimeError("synthetic primary failure")
                    self.assertIsNotNone(raised.exception.__cause__)
                    self.assertIn(
                        "synthetic cleanup failure",
                        str(raised.exception.__cause__),
                    )

    def test_prepare_cli_writes_json_failure_report_to_a_new_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / "nested/reports/release.json"
            with patch(
                "sys.argv",
                [
                    "prepare_release_bundle.py",
                    "--dist",
                    str(root / "missing-dist"),
                    "--wheelhouse",
                    str(root / "missing-wheelhouse"),
                    "--lock",
                    str(root / "missing.lock"),
                    "--output",
                    str(root / "release"),
                    "--version",
                    RELEASE_VERSION,
                    "--platform-label",
                    "linux-x86_64-py312",
                    "--report",
                    str(report),
                ],
            ), redirect_stdout(io.StringIO()):
                status = prepare_main()

            self.assertEqual(status, 1)
            document = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(document["ok"])

    def test_smoke_cli_writes_failure_report_to_a_new_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / "nested/reports/smoke.json"
            with patch(
                "scripts.fresh_wheel_smoke.smoke",
                side_effect=ValueError("synthetic smoke failure"),
            ), patch(
                "sys.argv",
                [
                    "fresh_wheel_smoke.py",
                    "--wheel",
                    str(root / "missing.whl"),
                    "--expected-version",
                    RELEASE_VERSION,
                    "--bundle-root",
                    str(root / "missing-bundle"),
                    "--output",
                    str(report),
                ],
            ), redirect_stdout(io.StringIO()):
                status = smoke_main()

            self.assertEqual(status, 1)
            document = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(document["ok"])


if __name__ == "__main__":
    unittest.main()
