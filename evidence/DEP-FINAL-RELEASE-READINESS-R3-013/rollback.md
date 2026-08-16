# Rollback

rollback_version: 3.0
target: complete experimental.8 final release-readiness candidate
rollback_action: git_revert
rollback_ref: 2d8497efe36f394637f8a224c70a32167f69bbd5
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if the complete candidate weakens trusted verification, Evidence integrity, safe rollback, or autonomy/approval boundaries.

## Reversible steps

# Revert the atomic implementation commit above; later Evidence/Gate/Receipt commits remain audit-only descendants.

## Data compatibility

# Schema-1.1 external-action state remains readable by Base. Reconciliation restores the Base-managed Agent governance set and removes candidate-only managed assets.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor, then run unittest and the complete reverted verification matrix.
