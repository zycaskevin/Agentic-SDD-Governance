# Rollback

rollback_version: 3.0
target: final experimental.8 autonomy and first-consumer readiness batch
rollback_action: git_revert
rollback_ref: eb9b64913cf9bbc3fc632a9dce6593c35b8646e3
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if exact package binding, owner-signature revalidation, trusted first-consumer verification, portable Proof enforcement, or routine L0/L1 autonomy regresses.

## Reversible steps

# Revert the immutable implementation commit above; Evidence-only descendants remain audit history.

## Data compatibility

# Pending schema-1.1 external actions remain readable. An unsigned local completed row fails closed and requires a new signed resolution or bounded replacement action ID.

## Post-rollback verification

# Refresh managed Agent governance from reverted source, run Doctor, then run the declared unittest module and the release-readiness matrix.
