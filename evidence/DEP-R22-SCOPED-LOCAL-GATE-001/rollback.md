# Rollback

rollback_version: 3.0
target: R22 scoped validation offline foundation
rollback_action: git_revert
rollback_ref: 8b1edf3414253259bbd2bd1e44d933361c155333
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

Revert if an R22 authority input, Gate configuration, or ambiguous change set
can be classified as unrelated to R22.

## Reversible steps

Revert the exact offline-foundation commit through the reviewed Git workflow.
Do not alter the current unconditional Local Green command.

## Data compatibility

No persistent data, trust-store, runtime configuration, or schema migration is
introduced.

## Post-rollback verification

Refresh managed Agent governance from the reverted source, run Doctor, then run
the R22 scope, CI Guard, and repository-contract test suites.
