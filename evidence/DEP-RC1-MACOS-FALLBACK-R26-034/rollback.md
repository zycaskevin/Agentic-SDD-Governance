# Rollback

rollback_version: 3.0
target: R26 macOS fallback expectation and the approved RC1 candidate product tree
rollback_action: git_revert
rollback_ref: 28a80236ba54d6b4ff17604ff3453a09c692047d
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Rollback if the R26 candidate fails the complete source, package, installed-wheel, or trusted-Base verification contract after merge.

## Reversible steps

# Revert the immutable product commit through the reviewed Git workflow. Evidence-only descendants remain audit records and are excluded from the restored product tree.

## Data compatibility

# No persistent application data migration is introduced. Reverting restores the exact trusted Base product tree outside audit paths.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor and validation, then run the Base unittest module and package-consumer proof.
