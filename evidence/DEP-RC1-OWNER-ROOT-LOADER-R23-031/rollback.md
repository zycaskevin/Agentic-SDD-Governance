# Rollback

rollback_version: 3.0
target: RC1 root Owner fixed-trust loader and bound Decision Contract update
rollback_action: git_revert
rollback_ref: 2c1f6d6f3a73e77cfc7d563ed4e20a1a3e2ad9b1
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Rollback if the Owner loader accepts a non-fixed path or non-root identity, any Agent path uses the Owner loader, fixed trust validation loses its descriptor/ownership/link/bounds/duplicate checks, or the rebuilt root Owner card cannot be produced from the exact reviewed artifact.

## Reversible steps

# Revert the immutable R23 product commit `2c1f6d6f3a73e77cfc7d563ed4e20a1a3e2ad9b1` through the reviewed Git workflow.

## Data compatibility

# No data or receipt schema changes. The R22 product receipt remains trusted-Base compatible. Reversion intentionally restores the unavailable root Owner card path and leaves the L2 decision unsigned/unmergeable.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor, then run `tests.test_owner_approval`, `tests.test_autonomy`, `tests.test_fs_security`, the full unittest suite, build/Twine, and installed-wheel checks. Confirm Agent root refusal remains fail-closed.
