# Rollback

rollback_version: 3.0
target: scoped decision Owner-client marker correction
rollback_action: git_revert
rollback_ref: 9b4a53dd0f008721c79e55740dff6118efb1abdd
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

Revert if the canonical marker occurs other than exactly once or the correction
changes Owner runtime behavior.

## Reversible steps

Revert the exact fix commit through the reviewed Git workflow.

## Data compatibility

No data, schema, receipt, trust-store, or runtime compatibility change.

## Post-rollback verification

Refresh governance, run Doctor, and rerun the R22 scope and Owner approval tests.
