# Rollback

rollback_version: 3.0
target: R28 CI compatibility and benchmark timeout product commit
rollback_action: git_revert
rollback_ref: 7784f00b0125e9e30fd056ccf8f8407135d102f0
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if omission can make Local Green unbounded, explicit invalid timeout values pass, non-exempt concurrency controls weaken, the benchmark loses exact-tree proof, or any protected authority boundary changes.

## Reversible steps

# Revert the immutable atomic R28 product commit through the reviewed Git workflow. Refresh managed Agent files only from the reverted source.

## Data compatibility

# Reverting restores R27's required timeout field. Existing explicit R27 configurations remain compatible; legacy schema-1.0 configurations that omit the field will again require a manual explicit value. The Owner Decision request, assumptions, receipt, and Owner-client identity are unchanged by R28.

## Post-rollback verification

# Run `sddgov setup-agent --agent codex --profile team-standard`, `sddgov doctor`, `sddgov validate`, the exact trusted-Base unittest suite, Base package build and Twine checks, and a fresh installed-wheel consumer smoke. Compare the reverted non-audit tree to exact trusted Base outside Evidence, Gate, and review receipts.

## Rehearsal result

# PASS. From the reviewed R28 Evidence head, `git revert --no-commit 7784f00b0125e9e30fd056ccf8f8407135d102f0` restored the exact trusted-Base non-audit tree. Reconciliation setup, Doctor, validation, 237 Base tests with one expected sandbox skip, Base wheel/sdist build, Twine checks, hash-locked dependency installation, `pip check`, and fresh installed-wheel setup/Doctor all completed successfully.
