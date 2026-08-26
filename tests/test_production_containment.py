from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from sddgov.production_containment import (
    CgroupLimits,
    ProductionContainmentViolation,
    RuntimeImage,
    SyntheticAtomicLauncher,
    SyntheticCgroupV2Scope,
    production_activation_permitted,
)


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


class ProductionContainmentFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="sddgov-af27-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root)

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux ELF")
    def test_verified_held_elf_fd_survives_path_replacement(self) -> None:
        runtime = self.root / "runtime"
        original = self.root / "original-runtime"
        replacement = self.root / "replacement"
        shutil.copy2(Path(sys.executable), runtime)
        shutil.copy2(Path(sys.executable), replacement)
        runtime.chmod(0o700)
        replacement.chmod(0o700)
        image = RuntimeImage.open_verified(
            runtime,
            expected_sha256=_digest(runtime),
            allowed_uids=frozenset({os.geteuid()}),
        )
        try:
            os.replace(runtime, original)
            os.replace(replacement, runtime)
            scope = SyntheticCgroupV2Scope(
                CgroupLimits(16, 64 * 1024 * 1024, "10000 100000")
            )
            scope.configure()
            launcher = SyntheticAtomicLauncher(scope)
            self.assertEqual(launcher.launch(image), image.descriptor)
            launcher.cleanup()
        finally:
            image.close()

    def test_script_runtime_is_rejected_before_execution(self) -> None:
        script = self.root / "runtime-script"
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(0o700)
        with self.assertRaisesRegex(ProductionContainmentViolation, "not_elf"):
            RuntimeImage.open_verified(
                script,
                expected_sha256=_digest(script),
                allowed_uids=frozenset({os.geteuid()}),
            )

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux ELF")
    def test_elf_hash_mismatch_is_rejected_before_execution(self) -> None:
        elf = self.root / "runtime-elf"
        shutil.copy2(Path(sys.executable).resolve(), elf)
        elf.chmod(0o700)
        with self.assertRaisesRegex(ProductionContainmentViolation, "hash_mismatch"):
            RuntimeImage.open_verified(
                elf,
                expected_sha256="sha256:" + "0" * 64,
                allowed_uids=frozenset({os.geteuid()}),
            )

    def test_scope_requires_limits_atomic_attach_kill_empty_then_remove(self) -> None:
        scope = SyntheticCgroupV2Scope(
            CgroupLimits(16, 64 * 1024 * 1024, "10000 100000")
        )
        with self.assertRaisesRegex(ProductionContainmentViolation, "atomic_attach"):
            scope.attach_at_launch()
        scope.configure()
        scope.attach_at_launch()
        with self.assertRaisesRegex(ProductionContainmentViolation, "atomic_attach"):
            scope.attach_at_launch()
        scope.kill_and_wait_empty()
        with self.assertRaisesRegex(ProductionContainmentViolation, "cleanup_invalid"):
            scope.kill_and_wait_empty()
        scope.remove()
        self.assertEqual(
            scope.events,
            [
                "limits_configured",
                "atomically_attached",
                "cgroup_kill",
                "populated_zero",
                "scope_removed",
            ],
        )

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux ELF")
    def test_launcher_passes_exact_held_fd_in_required_order(self) -> None:
        runtime = self.root / "runtime"
        shutil.copy2(Path(sys.executable).resolve(), runtime)
        runtime.chmod(0o700)
        image = RuntimeImage.open_verified(
            runtime,
            expected_sha256=_digest(runtime),
            allowed_uids=frozenset({os.geteuid()}),
        )
        scope = SyntheticCgroupV2Scope(
            CgroupLimits(8, 32 * 1024 * 1024, "5000 100000")
        )
        launcher = SyntheticAtomicLauncher(scope)
        try:
            with self.assertRaisesRegex(
                ProductionContainmentViolation, "launcher_state_invalid"
            ):
                launcher.launch(image)
            scope.configure()
            self.assertEqual(launcher.launch(image), image.descriptor)
            self.assertEqual(
                scope.events,
                ["limits_configured", "runtime_fd_verified", "atomically_attached"],
            )
            with self.assertRaisesRegex(
                ProductionContainmentViolation, "launcher_state_invalid"
            ):
                launcher.launch(image)
            launcher.cleanup()
            with self.assertRaisesRegex(
                ProductionContainmentViolation, "launcher_cleanup_invalid"
            ):
                launcher.cleanup()
        finally:
            image.close()

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux ELF")
    def test_held_runtime_metadata_drift_fails_closed(self) -> None:
        runtime = self.root / "runtime"
        alias = self.root / "runtime-hardlink"
        shutil.copy2(Path(sys.executable).resolve(), runtime)
        runtime.chmod(0o700)
        image = RuntimeImage.open_verified(
            runtime,
            expected_sha256=_digest(runtime),
            allowed_uids=frozenset({os.geteuid()}),
        )
        try:
            os.link(runtime, alias)
            with self.assertRaisesRegex(
                ProductionContainmentViolation, "fd_identity_changed"
            ):
                image.fileno()
        finally:
            image.close()

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux ELF")
    def test_closed_runtime_descriptor_fails_closed(self) -> None:
        runtime = self.root / "runtime"
        shutil.copy2(Path(sys.executable).resolve(), runtime)
        runtime.chmod(0o700)
        image = RuntimeImage.open_verified(
            runtime,
            expected_sha256=_digest(runtime),
            allowed_uids=frozenset({os.geteuid()}),
        )
        image.close()
        image.close()
        with self.assertRaisesRegex(
            ProductionContainmentViolation, "fd_unavailable"
        ):
            image.fileno()

    def test_production_activation_remains_denied(self) -> None:
        self.assertFalse(production_activation_permitted())


if __name__ == "__main__":
    unittest.main()
