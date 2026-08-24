# Rollback

rollback_version: 3.0
target: Issue #44 implementation commit
rollback_action: git_revert
rollback_ref: 5a1da394d7ad802488fe0218f69c9d9ceef216ab
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

# Trigger: revert if the bounded grammar accepts a bypass expression, rejects a
# documented legacy guard, or causes the governed CI/local-gate matrix to fail.
# Reversible steps: revert the immutable implementation commit through the
# reviewed Git workflow, then regenerate the managed Codex governance files.
# Data compatibility: no persisted data or schema changes are involved.
# Refresh managed Agent governance from the reverted source, run Doctor, then run the declared module and affected full verification matrix.
