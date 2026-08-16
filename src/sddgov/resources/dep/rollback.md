# Rollback

rollback_version: 2.0
target: TODO bounded rollback target
rollback_action: git_revert
rollback_ref: REPLACE_WITH_FULL_CANDIDATE_SHA
verify_action: python_module
verify_module: pytest

## Trigger

# Describe the machine-verifiable condition that requires rollback.

## Reversible steps

# Revert the immutable bounded commit through the reviewed Git workflow.

## Data compatibility

# State data and schema compatibility consequences.

## Post-rollback verification

# Run the declared module plus the affected full verification matrix.
