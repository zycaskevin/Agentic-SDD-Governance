# Rollback

rollback_version: 1.0
target: bounded experimental.8 security-hardening change
command: git revert --no-edit 576b49aa6b94d9fad2ff6be9ff7983d18a76abd2
verify: python -m pytest

## Trigger

# Rollback if the change weakens L2/L3 authority, clobbers later-writer data, cannot recover incomplete local Evidence state, or causes routine L0/L1 engineering to require owner approval.

## Reversible steps

# Revert the bounded implementation commit. Do not delete local raw DEP evidence; retain it for investigation. Consumers remain on the experimental.7 pre-release until a corrected candidate is independently reviewed.

## Data compatibility

# No Production or user data migration exists. Experimental.8 changes local governance state for external-actions.json and requires reissuing experimental.7 L2 receipts that used free-form reopen prose.

## Post-rollback verification

# Run the complete test suite, sddgov validate, sddgov ci verify, installed-agent doctor, strict verification of retained DEPs, and confirm no experimental.8 Release was published.
