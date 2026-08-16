# Rollback

rollback_version: 2.0
target: protected inventory for Agent-loaded experimental.8 governance copies
rollback_action: git_revert
rollback_ref: 140bf2be2c3d29aa52650c7a3282afdfde30ec7b
verify_action: python_module
verify_module: pytest

## Trigger

# The new protected patterns block a non-governance path that can be proven unrelated to Agent runtime loading.

## Reversible steps

# Revert the exact inventory commit with git revert; do not weaken protection while a related governed change is pending review.

## Data compatibility

# No persistent product data or schema changes are involved.

## Post-rollback verification

# Run Merge Gate and repository-contract tests and confirm every remaining runtime governance source stays protected.
