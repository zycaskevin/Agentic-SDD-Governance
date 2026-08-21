# Rollback

rollback_version: 3.0
target: bounded RC1 readiness and PR25 review fixes
rollback_action: git_revert
rollback_ref: 8459285df7e9d6c20039e2e9a752d561390e3ae2
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Roll back if the implementation weakens fail-closed classification, redaction, trusted-Base verification, exact-tree proof, or offline release isolation, or if the declared regressions no longer pass.

## Reversible steps

# Revert the immutable single-parent implementation commit through a reviewed incident branch. Preserve this DEP and later audit receipts; do not rewrite protected history.

## Data compatibility

# No Production data, schema migration, credential, external publication, or root service installation occurred. The revert restores the trusted Base commit's non-Evidence tree and experimental.8 managed resources.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor, then run unittest discovery. Confirm Base commit 1a5a0b214eccc2b9edd076fd5e2f222c4a456725 has tree 7b48daf1558a6ca3e02f20654663292a39772fce and that the revert result tree equals that tree object exactly outside declared Evidence/audit paths.
