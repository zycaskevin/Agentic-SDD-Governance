# Rollback

rollback_version: 3.0
target: complete RC1 R16 implementation candidate
rollback_action: git_revert
rollback_ref: c17508e16c5e773ca457e291cc2f7355ccdf65f8
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if the native matrix imports checkout source, exceeds the fixed Darwin
# staging boundary, fails real Linux/Darwin health/cleanup, or regresses any
# inherited RC1 hard gate.

## Reversible steps

# Revert the immutable single-parent product commit. R6-R16 Evidence, the Gate,
# and independent receipt remain audit descendants.

## Data compatibility

# No production migration exists. The revert restores exact Base code/schema
# while retaining audit history. No public RC1 package or authority store moved.

## Post-rollback verification

    # In an isolated clone, verify the rollback ref has exact Base as parent.
    # git revert --no-commit c17508e16c5e773ca457e291cc2f7355ccdf65f8
    # Prove exact Base outside evidence/**, gate, and review audit paths.
    # Install Base requirements-governance.lock with --require-hashes in a fresh
    # environment; run setup-agent, Doctor, Validate, and 229 Base tests.
    # Build/Twine and a fresh Base-wheel consumer remain required release checks.
    # Only after every command exits 0 is rollback Green.
