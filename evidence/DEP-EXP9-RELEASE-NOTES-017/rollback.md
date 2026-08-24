# Rollback

rollback_version: 3.0
target: Issue #46 implementation commit
rollback_action: git_revert
rollback_ref: bac2a59be8554cfe91fd058d4eed5928ff0c1d42
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

# Trigger: revert if the public sentence becomes inaccurate or the scoped
# privacy assertion no longer measures the intended release-note boundary.
# Reversible steps: revert the immutable implementation commit through the
# reviewed Git workflow, then refresh managed Codex governance.
# Data compatibility: no persisted data, schema, or runtime change is involved.
# Refresh managed Agent governance from the reverted source, run Doctor, then run the declared module and affected full verification matrix.
