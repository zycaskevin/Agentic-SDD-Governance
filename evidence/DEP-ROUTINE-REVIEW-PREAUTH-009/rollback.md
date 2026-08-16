# Rollback

rollback_version: 2.0
target: pre-authorized routine review sharing policy and adapters
rollback_action: git_revert
rollback_ref: fd691a7a069fbaa0f5d5f17886524a29f1ba17a4
verify_action: python_module
verify_module: pytest

## Trigger

# Revert if the policy permits sensitive or expanded third-party sharing without the required recorded decision or Operational Action.

## Reversible steps

# Revert the immutable implementation commit through the reviewed Git workflow; keep Issue and DEP history for audit.

## Data compatibility

# No product data, database, credential, or Production schema changes exist. Installed governance copies return to the prior review-routing behavior.

## Post-rollback verification

# Run repository-contract tests, complete tests, validate, CI verify, Local Green, and doctor; confirm no sensitive payload was sent by the reverted policy.
