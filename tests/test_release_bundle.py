import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
import zlib
from contextlib import redirect_stdout
from os import environ
from pathlib import Path
from unittest.mock import patch

from sddgov import __version__ as RELEASE_VERSION
from sddgov.broker import receive_broker_health_response
from sddgov.fs_security import canonicalize_platform_path, exclusive_rename_at

from scripts.fresh_wheel_smoke import (
    _fresh_smoke_temporary_directory,
    _installed_broker_smoke,
    _public_error as smoke_public_error,
    _receive_broker_health,
    _run,
    _snapshot_verified_bundle,
    _terminate_broker_process,
    main as smoke_main,
    verify_offline_bundle,
)
from scripts.prepare_release_bundle import main as prepare_main
from scripts.prepare_release_bundle import _public_error as bundle_public_error
from scripts.prepare_release_bundle import prepare_release_bundle
from scripts.release_files import open_directory, open_regular_file
from scripts.verify_release_assets import verify_release_assets


class ReleaseBundleTests(unittest.TestCase):
    @staticmethod
    def _health_readers():
        return (
            ("fresh-wheel", _receive_broker_health),
            (
                "product",
                lambda client: receive_broker_health_response(
                    client, timeout_seconds=1
                ),
            ),
        )

    @unittest.skipUnless(os.name == "posix", "POSIX temporary parent fallback")
    def test_fresh_smoke_workspace_falls_back_when_tmp_is_unavailable(self):
        original = tempfile.TemporaryDirectory
        with tempfile.TemporaryDirectory() as fallback:
            def create(*, prefix, dir):
                if dir == "/tmp":
                    raise PermissionError("synthetic unavailable short parent")
                return original(prefix=prefix, dir=dir)

            with (
                patch(
                    "scripts.fresh_wheel_smoke.tempfile.TemporaryDirectory",
                    side_effect=create,
                ),
                patch(
                    "scripts.fresh_wheel_smoke.tempfile.gettempdir",
                    return_value=fallback,
                ),
                _fresh_smoke_temporary_directory() as workspace,
            ):
                self.assertEqual(
                    Path(workspace).parent,
                    canonicalize_platform_path(Path(fallback)),
                )

    @unittest.skipUnless(os.name == "posix", "POSIX Darwin alias rehearsal")
    def test_fresh_smoke_canonicalizes_the_darwin_tmp_workspace(self):
        with (
            patch("scripts.fresh_wheel_smoke.sys.platform", "darwin"),
            _fresh_smoke_temporary_directory() as workspace,
        ):
            self.assertEqual(Path(workspace).parts[:3], ("/", "private", "tmp"))

    def test_broker_health_response_may_arrive_in_fragments(self):
        class FragmentedSocket:
            def __init__(self):
                self.fragments = [b"RE", b"AD", b"Y", b"\n"]

            def settimeout(self, _timeout):
                return None

            def recv(self, size):
                if not self.fragments:
                    return b""
                fragment = self.fragments.pop(0)
                if len(fragment) > size:
                    self.fragments.insert(0, fragment[size:])
                    return fragment[:size]
                return fragment

        for name, reader in self._health_readers():
            with self.subTest(reader=name):
                self.assertEqual(reader(FragmentedSocket()), b"READY\n")

    def test_broker_health_response_rejects_delayed_extra_bytes(self):
        class DelayedExtraSocket:
            def __init__(self):
                self.fragments = [b"READY\n", b"EXTRA", b""]

            def settimeout(self, _timeout):
                return None

            def recv(self, size):
                fragment = self.fragments.pop(0)
                if len(fragment) > size:
                    self.fragments.insert(0, fragment[size:])
                    return fragment[:size]
                return fragment

        for name, reader in self._health_readers():
            with self.subTest(reader=name):
                self.assertEqual(reader(DelayedExtraSocket()), b"READY\nE")

    def test_broker_health_response_is_bounded_on_oversize_data(self):
        class OversizeSocket:
            def settimeout(self, _timeout):
                return None

            def recv(self, size):
                return b"X" * size

        for name, reader in self._health_readers():
            with self.subTest(reader=name):
                self.assertEqual(reader(OversizeSocket()), b"X" * 7)

    def test_broker_health_response_stall_obeys_the_deadline(self):
        class StalledSocket:
            def __init__(self):
                self.calls = 0

            def settimeout(self, _timeout):
                return None

            def recv(self, _size):
                self.calls += 1
                if self.calls == 1:
                    return b"READY\n"
                raise TimeoutError("synthetic stalled response")

        for name, reader in self._health_readers():
            with self.subTest(reader=name), self.assertRaisesRegex(
                TimeoutError, "stalled response"
            ):
                reader(StalledSocket())

    def test_installed_broker_shutdown_drains_pipes_before_waiting(self):
        class FakeProcess:
            def __init__(self, socket_path):
                self.socket_path = socket_path
                self.returncode = None
                self.communicate_timeouts = []

            def poll(self):
                return self.returncode

            def send_signal(self, _signal):
                return None

            def communicate(self, timeout):
                self.communicate_timeouts.append(timeout)
                self.returncode = 0
                self.socket_path.unlink(missing_ok=True)
                return ("x" * 131072, "")

            def wait(self, timeout):
                raise AssertionError(f"wait called before pipe drain: {timeout}")

            def kill(self):
                self.returncode = -9

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def settimeout(self, _timeout):
                return None

            def connect(self, _path):
                return None

            def sendall(self, _data):
                return None

            def shutdown(self, _how):
                return None

            def recv(self, _size):
                if getattr(self, "sent", False):
                    return b""
                self.sent = True
                return b"READY\n"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = root / "installed-broker.sock"
            socket_path.touch()
            process = FakeProcess(socket_path)
            with patch(
                "scripts.fresh_wheel_smoke.subprocess.Popen", return_value=process
            ), patch(
                "scripts.fresh_wheel_smoke.socket.socket", return_value=FakeClient()
            ):
                result = _installed_broker_smoke(
                    Path("/synthetic/python"), root, {}
                )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(process.communicate_timeouts, [10, 1])

    def test_broker_shutdown_drains_more_than_a_pipe_buffer(self):
        code = r'''
import os
import signal
import sys
import time

def stop(_signal, _frame):
    os.write(sys.stdout.fileno(), b"O" * 131072)
    os.write(sys.stderr.fileno(), b"E" * 131072)
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
print("READY", flush=True)
while True:
    time.sleep(1)
'''
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(process.stdout.readline(), "READY\n")
            stdout, stderr = _terminate_broker_process(process)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
        self.assertEqual(len(stdout), 131072)
        self.assertEqual(len(stderr), 131072)

    def test_shareable_failure_reports_mask_local_paths(self):
        local_paths = (
            Path(tempfile.gettempdir()) / "sddgov-sensitive-build/input.whl",
            Path.home(),
            Path.home() / "Sensitive Build/input.whl",
            Path("/private/var/folders/zz/Sensitive Build/input.whl"),
            Path("/mnt/c/Users/Kevin/Sensitive Build/input.whl"),
            Path("//wsl.localhost/Ubuntu/home/kevin/Sensitive Build/input.whl"),
            Path(r"\\wsl.localhost\Ubuntu\home\kevin\Sensitive Build\input.whl"),
            Path(r"\\wsl$\Ubuntu\home\kevin\Sensitive Build\input.whl"),
        )
        for sanitizer in (smoke_public_error, bundle_public_error):
            for local in local_paths:
                with self.subTest(sanitizer=sanitizer.__module__, local=local):
                    rendered = sanitizer(f"failed to read {local}: denied")
                    self.assertNotIn(str(local), rendered)
                    self.assertNotIn("Sensitive Build/input.whl", rendered)
                    self.assertIn("<local-path>", rendered)

    def test_shareable_failure_reports_mask_escaped_wsl_unc_paths(self):
        native_paths = (
            r"\\wsl.localhost\Ubuntu\home\kevin\report.json",
            r"\\wsl.localhost\Ubuntu\home\kevin\Sensitive Build\input.whl",
            r"\\wsl$\Ubuntu\home\kevin\report.json",
            r"\\wsl$\Ubuntu\home\kevin\Sensitive Build\input.whl",
        )
        for sanitizer in (smoke_public_error, bundle_public_error):
            for native in native_paths:
                for value in (json.dumps(native), repr(native)):
                    with self.subTest(
                        sanitizer=sanitizer.__module__, value=value
                    ):
                        rendered = sanitizer(f"failed to read {value}: denied")
                        self.assertNotIn("wsl", rendered.casefold())
                        self.assertIn("<local-path>", rendered)

    def test_shareable_failure_reports_do_not_mask_home_prefix_siblings(self):
        home = Path.home()
        sibling = f"{home.parent}base/{home.name}/input.whl"
        for sanitizer in (smoke_public_error, bundle_public_error):
            with self.subTest(sanitizer=sanitizer.__module__):
                self.assertEqual(
                    sanitizer(f"failed to read {sibling}: denied"),
                    f"failed to read {sibling}: denied",
                )

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

    def test_downloaded_public_release_inventory_is_reverified(self):
        with tempfile.TemporaryDirectory() as temporary:
            _wheel, output, _report = self._prepare(Path(temporary))

            verified = verify_release_assets(output)

            self.assertTrue(verified["ok"])
            self.assertEqual(verified["asset_count"], 3)
            self.assertEqual(
                set(verified["assets"]),
                {
                    *(path.name for path in (output / "distributions").iterdir()),
                    next(output.glob("*-offline-*.zip")).name,
                },
            )

    def test_downloaded_release_tampering_or_unlisted_asset_fails_closed(self):
        for failure in ("tampered", "unlisted"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                _wheel, output, _report = self._prepare(Path(temporary))
                if failure == "tampered":
                    next((output / "distributions").glob("*.tar.gz")).write_bytes(
                        b"tampered"
                    )
                    message = "digest mismatch"
                else:
                    (output / "unlisted.txt").write_text(
                        "not inventoried\n", encoding="utf-8"
                    )
                    message = "does not exactly cover"

                with self.assertRaisesRegex(ValueError, message):
                    verify_release_assets(output)

    def test_downloaded_release_rejects_root_distribution_name_collision(self):
        with tempfile.TemporaryDirectory() as temporary:
            _wheel, output, _report = self._prepare(Path(temporary))
            distribution = next((output / "distributions").iterdir())
            (output / distribution.name).write_bytes(distribution.read_bytes())

            with self.assertRaisesRegex(ValueError, "ambiguous duplicate names"):
                verify_release_assets(output)

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

    def test_release_writer_close_failure_is_precommit_and_cleans_output(self):
        for operation in ("write_bytes", "write_from_descriptor", "binary_writer"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                original_close = os.close
                failed = False

                def close_regular_then_fail(descriptor):
                    nonlocal failed
                    metadata = os.fstat(descriptor)
                    original_close(descriptor)
                    if stat.S_ISREG(metadata.st_mode) and not failed:
                        failed = True
                        raise OSError("synthetic release output close failure")

                with open_directory(root, "release directory") as output, patch(
                    "scripts.release_files.os.close",
                    side_effect=close_regular_then_fail,
                ), self.assertRaisesRegex(OSError, "release output close failure"):
                    if operation == "write_bytes":
                        output.write_bytes("result.bin", b"owned bytes")
                    elif operation == "write_from_descriptor":
                        with tempfile.TemporaryFile() as source:
                            source.write(b"owned bytes")
                            source.seek(0)
                            output.write_from_descriptor(
                                "result.bin", source.fileno()
                            )
                    else:
                        with output.binary_writer("result.bin") as handle:
                            handle.write(b"owned bytes")

                self.assertTrue(failed)
                self.assertFalse((root / "result.bin").exists())
                self.assertEqual(list(root.glob(".sddgov.cleanup-pending-*")), [])

    def test_release_partial_write_failure_cleans_the_exact_partial_generation(self):
        for operation in ("write_bytes", "write_from_descriptor"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                original_write = os.write
                calls = 0

                def write_prefix_then_fail(descriptor, value):
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        return original_write(descriptor, value[:3])
                    if calls == 2:
                        raise OSError("synthetic partial release write failure")
                    return original_write(descriptor, value)

                with open_directory(root, "release directory") as output, patch(
                    "scripts.release_files.os.write",
                    side_effect=write_prefix_then_fail,
                ), self.assertRaisesRegex(OSError, "partial release write failure"):
                    if operation == "write_bytes":
                        output.write_bytes("result.bin", b"owned bytes")
                    else:
                        with tempfile.TemporaryFile() as source:
                            source.write(b"owned bytes")
                            source.seek(0)
                            output.write_from_descriptor(
                                "result.bin", source.fileno()
                            )

                self.assertEqual(calls, 2)
                self.assertFalse((root / "result.bin").exists())
                self.assertEqual(list(root.glob(".sddgov.cleanup-pending-*")), [])

    def test_release_directory_fsync_failure_rolls_back_every_writer(self):
        for operation in ("write_bytes", "write_from_descriptor", "binary_writer"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                original_fsync = os.fsync
                failed = False

                def fail_first_directory_fsync(descriptor):
                    nonlocal failed
                    metadata = os.fstat(descriptor)
                    if stat.S_ISDIR(metadata.st_mode) and not failed:
                        failed = True
                        raise OSError("synthetic release directory fsync failure")
                    original_fsync(descriptor)

                with open_directory(root, "release directory") as output, patch(
                    "scripts.release_files.os.fsync",
                    side_effect=fail_first_directory_fsync,
                ), self.assertRaisesRegex(OSError, "release directory fsync failure"):
                    if operation == "write_bytes":
                        output.write_bytes("result.bin", b"owned bytes")
                    elif operation == "write_from_descriptor":
                        with tempfile.TemporaryFile() as source:
                            source.write(b"owned bytes")
                            source.seek(0)
                            output.write_from_descriptor(
                                "result.bin", source.fileno()
                            )
                    else:
                        with output.binary_writer("result.bin") as handle:
                            handle.write(b"owned bytes")

                self.assertTrue(failed)
                self.assertFalse((root / "result.bin").exists())

    def test_release_cleanup_preserves_replacement_at_identity_claim_boundary(self):
        cases = ("write_bytes", "write_from_descriptor", "binary_writer")
        for operation in cases:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                owned = root / "owned-generation.bin"
                replacement = b"later writer generation\n"
                original_rename = os.rename
                original_fsync = os.fsync
                failed = False
                swapped = False

                def fail_first_regular_fsync(descriptor):
                    nonlocal failed
                    metadata = os.fstat(descriptor)
                    if (
                        operation != "binary_writer"
                        and stat.S_ISREG(metadata.st_mode)
                        and not failed
                    ):
                        failed = True
                        raise OSError("synthetic primary write failure")
                    original_fsync(descriptor)

                def replace_before_identity_claim(
                    source_directory,
                    source,
                    destination_directory,
                    destination,
                ):
                    nonlocal swapped
                    if (
                        source == "result.bin"
                        and ".cleanup-pending-" in destination
                        and not swapped
                    ):
                        original_rename(
                            source,
                            owned.name,
                            src_dir_fd=source_directory,
                            dst_dir_fd=source_directory,
                        )
                        replacement_fd = os.open(
                            source,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                            0o600,
                            dir_fd=source_directory,
                        )
                        try:
                            os.write(replacement_fd, replacement)
                            original_fsync(replacement_fd)
                        finally:
                            os.close(replacement_fd)
                        swapped = True
                    exclusive_rename_at(
                        source_directory,
                        source,
                        destination_directory,
                        destination,
                    )

                with open_directory(root, "release directory") as output, patch(
                    "scripts.release_files.os.fsync",
                    side_effect=fail_first_regular_fsync,
                ), patch(
                    "sddgov.fs_security.exclusive_rename_at",
                    side_effect=replace_before_identity_claim,
                ):
                    if operation == "write_bytes":
                        with self.assertRaisesRegex(
                            OSError, "synthetic primary write failure"
                        ):
                            output.write_bytes("result.bin", b"owned bytes")
                    elif operation == "write_from_descriptor":
                        with tempfile.TemporaryFile() as source, self.assertRaisesRegex(
                            OSError, "synthetic primary write failure"
                        ):
                            source.write(b"owned bytes")
                            source.seek(0)
                            output.write_from_descriptor(
                                "result.bin", source.fileno()
                            )
                    else:
                        with self.assertRaisesRegex(
                            RuntimeError, "synthetic primary write failure"
                        ):
                            with output.binary_writer("result.bin") as handle:
                                handle.write(b"owned bytes")
                                raise RuntimeError("synthetic primary write failure")

                self.assertTrue(swapped)
                self.assertEqual((root / "result.bin").read_bytes(), replacement)
                self.assertEqual(owned.read_bytes(), b"owned bytes")

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

    def test_prepare_cli_rejects_report_symlink_without_overwriting_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_parent = root / "reports"
            report_parent.mkdir()
            target = root / "preserve.json"
            target.write_text("preserve\n", encoding="utf-8")
            report = report_parent / "release.json"
            report.symlink_to(target)
            stdout = io.StringIO()
            with patch(
                "scripts.prepare_release_bundle.prepare_release_bundle",
                side_effect=ValueError("synthetic release failure"),
            ), patch(
                "sys.argv",
                [
                    "prepare_release_bundle.py",
                    "--dist",
                    str(root / "dist"),
                    "--wheelhouse",
                    str(root / "wheelhouse"),
                    "--lock",
                    str(root / "requirements.lock"),
                    "--output",
                    str(root / "release"),
                    "--version",
                    RELEASE_VERSION,
                    "--platform-label",
                    "linux-x86_64-py312",
                    "--report",
                    str(report),
                ],
            ), redirect_stdout(stdout):
                status = prepare_main()

            self.assertEqual(status, 1)
            self.assertTrue(report.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "preserve\n")
            document = json.loads(stdout.getvalue())
            self.assertFalse(document["ok"])
            self.assertIn("cannot write release report", document["error"])

    def test_prepare_cli_catches_compression_errors_without_local_path_leak(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_path = Path.home() / "Sensitive Build/input.whl"
            stdout = io.StringIO()
            with patch(
                "scripts.prepare_release_bundle.prepare_release_bundle",
                side_effect=zlib.error(f"corrupt stream at {private_path}: invalid"),
            ), patch(
                "sys.argv",
                [
                    "prepare_release_bundle.py",
                    "--dist",
                    str(root / "dist"),
                    "--wheelhouse",
                    str(root / "wheelhouse"),
                    "--lock",
                    str(root / "requirements.lock"),
                    "--output",
                    str(root / "release"),
                    "--version",
                    RELEASE_VERSION,
                    "--platform-label",
                    "linux-x86_64-py312",
                ],
            ), redirect_stdout(stdout):
                status = prepare_main()

            self.assertEqual(status, 1)
            self.assertNotIn(str(Path.home()), stdout.getvalue())
            self.assertNotIn("Sensitive Build/input.whl", stdout.getvalue())
            self.assertIn("<local-path>", stdout.getvalue())

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

    def test_smoke_cli_rejects_report_symlink_without_overwriting_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_parent = root / "reports"
            report_parent.mkdir()
            target = root / "preserve.json"
            target.write_text("preserve\n", encoding="utf-8")
            report = report_parent / "smoke.json"
            report.symlink_to(target)
            stdout = io.StringIO()
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
            ), redirect_stdout(stdout):
                status = smoke_main()

            self.assertEqual(status, 1)
            self.assertTrue(report.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "preserve\n")
            document = json.loads(stdout.getvalue())
            self.assertFalse(document["ok"])
            self.assertIn("cannot write smoke report", document["error"])


if __name__ == "__main__":
    unittest.main()
