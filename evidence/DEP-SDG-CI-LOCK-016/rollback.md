# Rollback

rollback_version: 3.0
target: current-user Local Green cross-checkout serialization
rollback_action: git_revert
rollback_ref: 196685c2680da9a84d4b5efd35dd66f20909f1b4
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Rollback if the lock is bypassable, unsafe, changes command results, leaks
# repository data, deadlocks after process exit, or breaks a supported platform
# without the documented fail-closed behavior.

## Reversible steps

# Revert the immutable implementation-only commit above. This removes the helper,
# orchestration wrapper, focused tests, documentation, Work Package, and Issue;
# later DEP, Gate, and Review records remain audit-only descendants.

## Data compatibility

# No data, schema, credential, trust, payment, deployment, or repository command
# state is migrated. The persistent empty lock record may be removed separately
# only after confirming no Local Green process holds it; removal is not needed
# for functional rollback.

## Post-rollback verification

# Refresh the managed Codex governance copy from the reverted source, run Doctor,
# then run `python -m unittest`, source validation, and `git diff --check`.
# Confirm the revert does not change autonomy, merge, Reviewer, Evidence, or
# consumer-repository contracts outside this bounded implementation.
