# Rollback

rollback_version: 2.0
target: strict rollback v1-to-v2 verifier migration bridge
rollback_action: git_revert
rollback_ref: 576b49aa6b94d9fad2ff6be9ff7983d18a76abd2
verify_action: python_module
verify_module: pytest

## Trigger

# The bridge accepts any legacy command outside the exact allowlist, weakens v2 validation, or fails the trusted hosted verifier.

## Reversible steps

# Revert the bounded bridge commit with git revert; keep PR #12 unmerged and do not rerun the failed hosted revision.

## Data compatibility

# No data, schema, trust-store, or Production state migration is introduced.

## Post-rollback verification

# Run all rollback parser and full Merge Gate tests; both legacy broadening and v2 regression must fail closed.
