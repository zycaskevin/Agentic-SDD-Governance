# Rollback

rollback_version: 2.0
target: bounded experimental.8 rollback validator hardening
rollback_action: git_revert
rollback_ref: d7e16f2e5695f6fba28c262daf8e6819dd0c0c35
verify_action: python_module
verify_module: pytest

## Trigger

# Rollback if Base scoping, strict parsing, or candidate-range verification weakens or blocks the canonical reviewed plan.

## Reversible steps

# Revert the bounded implementation commit after binding its exact full SHA; do not Merge the vulnerable candidate.

## Data compatibility

# No Production data, schema, credentials, or external state changes are involved.

## Post-rollback verification

# Run hostile rollback tests, the full suite, validate, CI verify, and strict portable DEP verification.
