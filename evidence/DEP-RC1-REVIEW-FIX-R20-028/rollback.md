# Rollback

rollback_version: 3.0
target: complete RC1 R20 implementation candidate
rollback_action: git_revert
rollback_ref: d663d77af38aaae4fa067b2380376dbe3c75f886
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if UNC paths survive redaction, a failed multi-file call leaks an owned output or deletes a later writer, Darwin aliases fail, source validation runs after packaging, Broker shutdown can deadlock, or an inherited gate fails.

## Reversible steps

# Revert the immutable single-parent R20 product commit. R6-R20 Evidence and the Gate/receipt remain audit descendants.

## Data compatibility

# No production migration exists. Revert restores exact Base product state while preserving audit history. No release or authority store moved.

## Post-rollback verification

    # Verify rollback_ref has exact Base as parent, then run git revert with no commit for d663d77af38aaae4fa067b2380376dbe3c75f886. Prove the non-audit product tree equals Base; run Base setup-agent, Doctor, Validate, all 229 tests, locked build/Twine, and a clean wheel consumer. Only after every command exits 0 is rollback Green.
