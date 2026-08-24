# Rollback

rollback_version: 3.0
target: R30 atomic product commit for multiline quoted streaming redaction
rollback_action: git_revert
rollback_ref: 01e882a3a2a8fa98fc062110fdc0f273b03065c8
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert the atomic R30 product commit if streaming publishes any bounded
# multiline quoted sensitive value, diverges from whole-text redaction for the
# covered field, deletes a later writer, or weakens an existing fail-closed rule.

## Reversible steps

# Run the trusted declarative `git_revert` action for
# `01e882a3a2a8fa98fc062110fdc0f273b03065c8` in an isolated checkout. Refresh
# managed Codex governance from reverted source and retain no candidate output.

## Data compatibility

# No ledger, receipt, schema, trust root, or Production data migration is
# introduced. The existing Owner approval receipt and assumptions remain valid.

## Post-rollback verification

# Refresh managed Agent governance from reverted source, run Doctor and
# repository validation, execute the trusted Base unittest module, rebuild the
# Base package, and confirm the non-audit product tree equals the exact Base.
