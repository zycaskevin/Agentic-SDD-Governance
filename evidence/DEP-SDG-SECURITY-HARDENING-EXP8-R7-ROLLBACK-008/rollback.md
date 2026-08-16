# Rollback

rollback_version: 2.0
target: bounded experimental.8 conflict-proof rollback hardening
rollback_action: git_revert
rollback_ref: REPLACE_WITH_FULL_CANDIDATE_SHA
verify_action: python_module
verify_module: pytest

## Trigger

# Rollback if the tree simulation can be bypassed, executes candidate instructions, or rejects the canonical implementation-only commit.

## Reversible steps

# Revert the immutable implementation-only commit through the reviewed Git workflow; Evidence and audit receipts remain available for investigation.

## Data compatibility

# No Production data, schema, credential, or external-state change exists.

## Post-rollback verification

# Run the full test suite, validate, CI verification, strict DEP checks, installed-agent doctor, and offline synthetic pilot.
