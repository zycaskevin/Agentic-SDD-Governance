# Rollback

rollback_version: 3.0
target: complete RC1 R14 implementation candidate
rollback_action: git_revert
rollback_ref: 9e8bd708fbfea7a995d6256a4b2e5f9e04d2c9d7
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R14 admits a vulnerable release tool, removes a replacement socket,
# strands its own socket, leaks sensitive Broker data, restores ownerless macOS
# pathname rotation, or regresses any inherited RC1 hard gate.

## Reversible steps

# Revert the immutable single-parent product commit. R6-R14 Evidence, the Gate,
# and independent receipt remain audit descendants.

## Data compatibility

# No production migration exists. The revert restores exact Base code/schema
# while retaining audit history. No public RC1 package or authority store moved.

## Post-rollback verification

    # In an isolated checkout, verify the rollback ref has exact Base as parent.
    # git revert --no-commit 9e8bd708fbfea7a995d6256a4b2e5f9e04d2c9d7
    # Prove exact Base outside evidence/** and gate/review audit paths.
    # Install Base requirements-governance.lock with --require-hashes in a new
    # no-system-site environment; run setup-agent, Doctor, Validate, and tests.
    # Use a separate hash-locked release environment because Base predates
    # requirements-release.lock; run build --no-isolation and Twine.
    # Install the Base wheel plus locked dependencies in a third clean consumer;
    # assert 0.2.0-experimental.8, setup-agent, Doctor, and pip check.
    # Reconciliation may refresh only manifest installed_at metadata.
    # Only after every command exits 0 is rollback Green.
