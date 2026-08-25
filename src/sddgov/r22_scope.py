"""Fail-closed path classification for the R22 approval boundary.

This module is deliberately not wired into Local Green yet.  It is an offline
foundation for a separately approved policy change: R22 verification may be
skipped only when an exact, trusted change set proves that no R22 authority
input or verifier implementation changed.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable


R22_PROTECTED_PATHS = frozenset(
    {
        ".sddgov/ci-cost-guard.json",
        ".sddgov/decisions.json",
        ".sddgov/trusted-approvers.json",
        "docs/HARD_GATES_V1_2.md",
        "docs/OWNER_KEY_CEREMONY.md",
        "policies/autonomy-policy.json",
        "schemas/product-decision-approval-receipt.schema.json",
        "src/sddgov/__init__.py",
        "src/sddgov/autonomy.py",
        "src/sddgov/fs_security.py",
        "src/sddgov/governance.py",
        "src/sddgov/owner_approval.py",
        "src/sddgov/owner_cli.py",
        "src/sddgov/owner_launcher.sh",
        "src/sddgov/r22_scope.py",
        "src/sddgov/trust.py",
        "tests/test_autonomy.py",
        "tests/test_fs_security.py",
        "tests/test_owner_approval.py",
        "tests/test_repository_contract.py",
        "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.md",
        "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json",
    }
)

R22_PROTECTED_PREFIXES = ("src/sddgov/resources/governance/",)


def _canonical_repository_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("R22 change path must be a non-empty string")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or "\\" in value
        or pure.as_posix() != value
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ValueError("R22 change path must be a canonical repository-relative POSIX path")
    return pure.as_posix()


def requires_r22_validation(changed_paths: Iterable[str] | None) -> bool:
    """Return whether one exact, non-empty changed path set touches R22.

    Absence of a trustworthy change set is fail closed.  The eventual executor
    must obtain paths from a trusted Base-bound diff, never from a candidate
    supplied CLI argument or mutable working-tree manifest.
    """

    if changed_paths is None:
        return True
    paths = tuple(_canonical_repository_path(value) for value in changed_paths)
    if not paths:
        return True
    return any(
        path in R22_PROTECTED_PATHS
        or any(path.startswith(prefix) for prefix in R22_PROTECTED_PREFIXES)
        for path in paths
    )
