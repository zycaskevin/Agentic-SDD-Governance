# Rollback

rollback_version: 3.0
target: complete R6 review-hardening implementation candidate
rollback_action: git_revert
rollback_ref: 4e45b924751d9bf4960972fad965b308a2cb8acb
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R6 weakens release-byte binding, Evidence integrity, Broker isolation,
# exact-tree rollback, or installed-governance compatibility.

## Reversible steps

# Revert the immutable single-parent implementation commit above; later Evidence,
# Gate, and review receipt commits remain audit-only descendants.

## Data compatibility

# No Production data migration is introduced. Reconciliation restores the Base
# managed resources and CI schema; R6 Evidence remains an immutable audit record.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor, unittest,
# package/fresh-wheel checks applicable to Base, and the exact-tree comparison.
