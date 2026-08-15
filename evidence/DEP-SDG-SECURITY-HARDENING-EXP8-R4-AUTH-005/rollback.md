# Rollback

rollback_version: 2.0
target: L2 existing-decision reuse package exclusion for experimental.8
rollback_action: git_revert
rollback_ref: HEAD
verify_action: python_module
verify_module: pytest

## Trigger

Exact package-free reuse regresses and cannot be repaired within the same bounded change.

## Reversible steps

Revert the exact classifier commit with `git revert`; do not release the vulnerable mixed-envelope candidate.

## Data compatibility

No data or decision-store migration is introduced.

## Post-rollback verification

Run autonomy and full tests, preserving fail-closed handling of nested and top-level foreign authority fields.
