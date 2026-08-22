# Rollback

rollback_version: 3.0
target: complete RC1 R19 implementation candidate
rollback_action: git_revert
rollback_ref: d7f40bcd1929aaab5c2327e69b7ffd2bc58a0ae0
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if cleanup deletes a later writer, reports follow symlinks, supported
# paths leak/fail, health accepts extra bytes, withdrawals hide unregistered
# artifacts, or any inherited RC1 hard gate fails.

## Reversible steps

# Revert the immutable single-parent R19 product commit. R6-R19 Evidence and
# the Gate/receipt remain audit descendants.

## Data compatibility

# No production migration exists. Revert restores exact Base product state
# while preserving audit history. No release or authority store moved.

## Post-rollback verification

    # Verify rollback_ref has exact Base as parent, then run:
    # git revert --no-commit d7f40bcd1929aaab5c2327e69b7ffd2bc58a0ae0
    # Prove non-audit product tree equals Base; run Base setup-agent, Doctor,
    # Validate, all 229 tests, locked build/Twine, and clean wheel consumer.
    # Only after every command exits 0 is rollback Green.
