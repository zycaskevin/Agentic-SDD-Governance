# Rollback

rollback_version: 2.0
target: release readiness rollback and single-run CI hardening
rollback_action: git_revert
rollback_ref: a0082496255bab3765161b913ae7b67928107236
verify_action: python_module
verify_module: unittest
# reconcile_action: setup_agent_from_reverted_source
# reconcile_agent: codex
# reconcile_profile: team-standard
# post_verify_action: doctor_and_python_module

## Trigger

# Rollback if the trusted verifier boundary is weakened, the required PR check is
# suppressed, candidate code is executed in the privileged hosted job, or the
# declared rollback cannot restore the previous healthy installed-governance state.

## Reversible steps

# Revert immutable implementation commit
# `a0082496255bab3765161b913ae7b67928107236` through the reviewed Git workflow.
# The exact v2-to-v3 bridge comments above require the candidate verifier to
# reconcile managed Codex governance from the reverted source before Doctor and
# the declared test module run.

## Data compatibility

# No application data or schema changes are present. The rollback restores the
# previous CI trigger and policy copies, then reconciles installed governance to
# the reverted source version.

## Post-rollback verification

# In a disposable clone at the reviewed Head, revert the immutable commit, run
# `setup-agent --force --agent codex --profile team-standard` from the reverted
# source, then require Doctor and the full `unittest` suite to pass.
