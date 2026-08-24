# Rollback

rollback_version: 3.0
target: TODO bounded rollback target
rollback_action: git_revert
rollback_ref: REPLACE_WITH_FULL_CANDIDATE_SHA
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Describe the machine-verifiable condition that requires rollback.

## Reversible steps

# Revert the immutable bounded commit through the reviewed Git workflow.

## Data compatibility

# State data and schema compatibility consequences.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor, then run the declared module and affected full verification matrix.
