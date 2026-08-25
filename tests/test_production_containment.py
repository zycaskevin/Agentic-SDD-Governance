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

    def test_verified_held_elf_fd_survives_path_replacement(self) -> None:
        runtime = self.root / "runtime"
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
            os.replace(replacement, runtime)
            image.verify_held_identity()
        finally:
            image.close()

    def test_script_or_hash_mismatch_is_rejected_before_execution(self) -> None:
        script = self.root / "runtime-script"
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(0o700)
        with self.assertRaisesRegex(ProductionContainmentViolation, "not_elf"):
            RuntimeImage.open_verified(
                script,
                expected_sha256=_digest(script),
                allowed_uids=frozenset({os.geteuid()}),
            )
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
        scope = SyntheticCgroupV2Scope(CgroupLimits(16, 64 * 1024 * 1024, "10000 100000"))
        with self.assertRaisesRegex(ProductionContainmentViolation, "atomic_attach"):
            scope.attach_at_launch()
        scope.configure()
        scope.attach_at_launch()
        scope.kill_and_wait_empty()
        scope.remove()
        self.assertEqual(
            scope.events,
            ["limits_configured", "atomically_attached", "cgroup_kill", "populated_zero", "scope_removed"],
        )

    def test_production_activation_remains_denied(self) -> None:
        self.assertFalse(production_activation_permitted())


if __name__ == "__main__":
    unittest.main()
