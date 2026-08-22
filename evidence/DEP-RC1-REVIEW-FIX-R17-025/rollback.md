# Rollback

rollback_version: 3.0
target: complete RC1 R17 implementation candidate
rollback_action: git_revert
rollback_ref: b827040cb8d8315cfd93afb309e4f9bf579775c9
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if public errors expose a host-local path, report output follows or
# overwrites a filesystem object, compressed-stream failures escape structured
# handling, current risk metadata diverges, or any inherited RC1 gate regresses.

## Reversible steps

# Revert the immutable single-parent R17 product commit. R6-R17 Evidence, the
# Gate, and independent receipt remain audit descendants.

## Data compatibility

# No production migration exists. The revert restores exact Base code/schema
# while retaining audit history. No public RC1 package or authority store moved.

## Post-rollback verification

    # In an isolated clone, verify the rollback ref has exact Base as parent.
    # git revert --no-commit b827040cb8d8315cfd93afb309e4f9bf579775c9
    # Prove exact Base outside evidence/**, gate, and review audit paths.
    # Install Base requirements-governance.lock with --require-hashes in a fresh
    # environment; run setup-agent, Doctor, Validate, and all 229 Base tests.
    # Build and Twine-check the Base wheel/sdist in a locked release-tool env.
    # Only after every command exits 0 is rollback Green.
