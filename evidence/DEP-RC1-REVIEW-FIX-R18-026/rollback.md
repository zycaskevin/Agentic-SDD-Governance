# Rollback

rollback_version: 3.0
target: complete RC1 R18 implementation candidate
rollback_action: git_revert
rollback_ref: b4154c3ebe9215d1397fb069e9b623ef76100d4b
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if reachable-commit traversal omits a candidate commit, an Evidence
# read can allocate past its ceiling, report publication follows a symlink,
# current shareable output exposes a local path, or any inherited RC1 gate fails.

## Reversible steps

# Revert the immutable single-parent R18 product commit. R6-R18 Evidence, the
# withdrawal registry, Gate, and independent receipt remain audit descendants.

## Data compatibility

# No production migration exists. Revert restores the exact Base product tree
# while preserving immutable audit history. No release or authority store moved.

## Post-rollback verification

    # In a full isolated clone, verify rollback_ref has exact Base as parent.
    # git revert --no-commit b4154c3ebe9215d1397fb069e9b623ef76100d4b
    # Prove the non-audit product tree equals exact Base.
    # Install Base requirements-governance.lock in a fresh environment; run
    # setup-agent, Doctor, Validate, and all 229 Base tests.
    # Build and Twine-check the Base wheel/sdist in a locked release-tool env.
    # Only after every command exits 0 is rollback Green.
