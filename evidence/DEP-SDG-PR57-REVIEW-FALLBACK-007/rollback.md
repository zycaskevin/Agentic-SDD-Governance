# Rollback

rollback_version: 4.0
target: bounded external reviewer fallback product decision
rollback_action: git_revert
rollback_ref: a5589c5f2d1904a13a1d9da4677aa6354cb3ef39
reconcile_action: assert_self_governance_deactivated
verify_action: self_governance_deactivated

## Trigger

# Revert if the fallback suppresses valid findings, removes independent review, weakens the full Gate, or activates repository self-governance.

## Reversible steps

# Revert the immutable product commit through the reviewed Git workflow.

## Data compatibility

# No production data, installation, external authority, tag, registry, or publication state changes.

## Post-rollback verification

# Apply the no-commit revert in a disposable checkout and require exact Base restoration plus absence of SDG activation paths.
