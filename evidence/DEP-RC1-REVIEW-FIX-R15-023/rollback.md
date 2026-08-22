# Rollback

rollback_version: 3.0
target: complete RC1 R15 implementation candidate
rollback_action: git_revert
rollback_ref: d2a3632a8e281552ac117a5b7db47fa73cb8f29f
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if staged publication overwrites a final endpoint, removes a replacement,
# strands its own verified entry, fails native Broker health/restart, admits a
# transient non-audit commit edge, or regresses any inherited RC1 hard gate.

## Reversible steps

# Revert the immutable single-parent product commit. R6-R15 Evidence, the Gate,
# and independent review receipt remain immutable audit descendants.

## Data compatibility

# No production migration exists. The revert restores exact Base code/schema
# while retaining audit history. No public RC1 package or authority store moved.

## Post-rollback verification

    # In an isolated clone, verify the rollback ref has exact Base as parent.
    # git revert --no-commit d2a3632a8e281552ac117a5b7db47fa73cb8f29f
    # Prove exact Base outside evidence/**, gate, and review audit paths.
    # Install Base requirements-governance.lock with --require-hashes in a fresh
    # no-system-site environment; run setup-agent, Doctor, Validate, and tests.
    # Build with the separately hash-locked release environment; run Twine.
    # Install the Base wheel plus locked dependencies in a fresh consumer; assert
    # 0.2.0-experimental.8, pip check, setup-agent, and Doctor.
    # Only after every command exits 0 is rollback Green.
