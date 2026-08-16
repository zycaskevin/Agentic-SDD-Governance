# Rollback

rollback_version: 3.0
target: final autonomy review findings and installed governance synchronization
rollback_action: git_revert
rollback_ref: d592892246b1dcfe6cffe50bfd90ea0feeec1227
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if malformed input can again become ACTION_REQUIRED, uncertainty prompts the owner, terminal cancellation loses owner-signature verification, or installed governance drifts from the reverted source.

## Reversible steps

# Revert the immutable implementation commit above; keep this Evidence-only descendant as audit history.

## Data compatibility

# Schema-1.1 external-action state remains readable. A cancelled/completed row without a valid owner-signed envelope fails closed and may require a new bounded action generation.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor, then run unittest and the complete release-readiness matrix.
