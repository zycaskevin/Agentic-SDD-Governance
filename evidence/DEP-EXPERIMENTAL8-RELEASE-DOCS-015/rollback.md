# Rollback

rollback_version: 3.0
target: experimental.8 release documentation correction
rollback_action: git_revert
rollback_ref: b09edcf65a57ce5f01c26eca1419dfa5f3395a7f
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if a scoped command selects a tag other than experimental.8, checksum verification is weakened, or the documentation claims an unverified delivery state.

## Reversible steps

# Revert `b09edcf65a57ce5f01c26eca1419dfa5f3395a7f` through the reviewed Git workflow in a disposable credential-free clone.

## Data compatibility

# Documentation only; no runtime state, Schema, dependency, Evidence contract, or user data migration is involved.

## Post-rollback verification

# In a disposable, credential-free, network-isolated clone, refresh managed Codex governance from the reverted source, run Doctor, execute `python -m unittest`, and rerun the exact version-reference assertion. Never run rollback verification in a live checkout.
