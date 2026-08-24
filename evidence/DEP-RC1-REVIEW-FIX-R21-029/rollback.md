# Rollback

rollback_version: 3.0
target: complete RC1 R21 implementation candidate
rollback_action: git_revert
rollback_ref: 642f21db6e08a80aba0819aa0fd8f2c0e20eecf4
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if staged bytes can be substituted, failed cleanup deletes a later writer or leaves an owned public generation, sensitive representations bypass redaction, a trusted dirfd triggers pathname mutation, release provenance is incomplete, or an inherited gate fails.

## Reversible steps

# Revert the immutable single-parent R21 product commit. R6-R21 Evidence and the Gate/receipt remain audit descendants.

## Data compatibility

# No production migration exists. Revert restores exact Base product state while preserving audit history. No release or authority store moved.

## Post-rollback verification

    # Verify rollback_ref has exact Base as parent, then run git revert with no commit for 642f21db6e08a80aba0819aa0fd8f2c0e20eecf4. Prove the non-audit product tree equals Base; run Base setup-agent, Doctor, Validate, all Base tests, locked build/Twine, and a clean wheel consumer. Only after every command exits 0 is rollback Green.
