# Rollback

rollback_version: 3.0
target: AF27 containment foundation and local-gate test repair
rollback_action: git_revert
rollback_ref: 372a36fd9cd5d8bac4c436dbe5d5451a9fa9f6a0
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

Revert if AF27 permits production activation, host cgroup creation, a runtime
execution path, or fails the held-FD and containment-ordering contracts.

## Reversible steps

Revert the exact two-commit AF27 implementation boundary through the reviewed
Git workflow; retain AF26 production hard-deny.

## Data compatibility

No persistent data, runtime configuration, service unit or schema migration.

## Post-rollback verification

Refresh managed Agent governance from reverted source, run Doctor, then run
unittest and the affected Local Green matrix.
