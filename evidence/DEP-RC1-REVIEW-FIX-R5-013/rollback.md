# Rollback

rollback_version: 3.0
target: bounded RC1 readiness and PR25/PR26 review fixes
rollback_action: git_revert
rollback_ref: 05822d004e84c13d4e5bc6e3967e798b675348ed
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Roll back if the implementation weakens trusted-Base verification, action classification, signatures, Broker separation, transactional redaction, exact-tree rollback, offline release inventory, or if the declared regressions no longer pass.

## Reversible steps

# Revert the immutable single-parent implementation commit through a reviewed incident branch. Preserve this DEP and later Gate/Review audit records; never rewrite protected history or use a force push.

## Data compatibility

# No Production data, schema migration, registry artifact, real credential/key, GitHub release configuration, or root service installation occurred. The revert restores the trusted Base non-Evidence tree and experimental.8 managed resources.

## Post-rollback verification

# Refresh managed Agent governance from reverted source, run Doctor, then unittest discovery. Confirm Base commit 1a5a0b214eccc2b9edd076fd5e2f222c4a456725 has tree 7b48daf1558a6ca3e02f20654663292a39772fce and the revert result equals that exact tree outside later Evidence/audit descendants.
