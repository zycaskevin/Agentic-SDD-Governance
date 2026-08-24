# Rollback

rollback_version: 3.0
target: R29 atomic product commit for the Broker consuming-client contract
rollback_action: git_revert
rollback_ref: d032da0eca496156f1c82be3784c5f3073325ac6
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert the atomic R29 product commit if the nonce-consuming path accepts a
# Broker socket that readiness rejects, if valid exact platform sockets stop
# working, or if the change weakens signature, nonce, or trusted-Base gates.

## Reversible steps

# Run the trusted declarative `git_revert` action for
# `d032da0eca496156f1c82be3784c5f3073325ac6` in an isolated checkout. Refresh
# the managed Codex governance files from reverted source and do not retain any
# candidate service or authority configuration.

## Data compatibility

# No ledger, receipt, schema, or Production data migration is introduced. A
# revert restores the trusted Base consumer behavior and invalidates this R29
# Owner-client binding.

## Post-rollback verification

# Refresh managed Agent governance from reverted source, run Doctor, validate
# the repository, run the trusted Base full unittest module, rebuild the Base
# wheel, and confirm the non-audit product tree equals the exact Base.
