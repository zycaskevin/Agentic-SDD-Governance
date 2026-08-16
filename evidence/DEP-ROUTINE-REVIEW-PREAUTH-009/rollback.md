# Rollback

rollback_version: 3.0
target: pre-authorized routine review sharing policy and adapters
rollback_action: git_revert
rollback_ref: fd691a7a069fbaa0f5d5f17886524a29f1ba17a4
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if the policy permits sensitive or expanded third-party sharing without the required recorded decision or Operational Action.

## Reversible steps

# Revert the immutable implementation commit through the reviewed Git workflow; keep Issue and DEP history for audit.

## Data compatibility

# No product data, database, credential, or Production schema changes exist. Installed governance copies return to the prior review-routing behavior.

## Post-rollback verification

# Load `sddgov` from the reverted source, refresh managed Agent governance with the recorded agent/profile, run Doctor and unittest, then validate CI and the Local Green Gate. Confirm the review-sharing route is absent and no sensitive payload was sent by the reverted policy.
