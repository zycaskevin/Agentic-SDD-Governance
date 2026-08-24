# Rollback

rollback_version: 3.0
target: R27 call-wide decision snapshot and bounded Local Green product commit
rollback_action: git_revert
rollback_ref: 06e528d39fcbb156ed7352bd4e0e40b2b2698a33
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R27 accepts different request/assumption generations in one stored decision verification, bypasses the smallest retained-file byte bound, weakens Owner/Agent authority separation, or reports Green after a timed-out command.

## Reversible steps

# Revert the final atomic R27 product commit through the reviewed Git workflow. Refresh the managed Agent files only from the reverted source. The immutable reference above is the final receipt-bearing product SHA reviewed by this DEP.

## Data compatibility

# The CI Cost Guard contract gains one required bounded timeout field. Reverting restores the previous schema and templates. The prior Owner receipt remains invalid for R27 because its signed Owner-client assumption changed; rollback does not reactivate or fabricate a receipt.

## Post-rollback verification

# Run `sddgov setup-agent --agent codex --profile team-standard`, `sddgov doctor`, `sddgov validate`, the Base full unittest suite, Base package build/Twine checks, and a fresh installed-wheel consumer smoke. Compare the reverted non-audit tree to exact trusted Base outside Evidence, Gate, and review receipts.
