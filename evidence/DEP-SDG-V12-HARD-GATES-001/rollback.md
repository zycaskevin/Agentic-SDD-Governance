# Rollback

## Trigger

A Hard Gate authorizes a dangerous action, permits receipt reuse, accepts an invalid signer, or blocks canonical reversible L0/L1 work without a machine-correctable reason.

## Reversible steps

Revert the single bounded Hard Gates commit and restore the previous workflow. Preserve existing v1.2 Production, L2/L3, Redaction, DEP, test, and SHA-256 integrity gates. Remove no user Evidence or state.

rollback_version: 1.0
target: GitHub merge commit for PR #5
command: git revert "$MERGE_COMMIT_SHA"
verify: python3 -m unittest discover -s tests -v

## Data compatibility

The change does not mutate Production data. Existing `.sddgov/decisions.json` L2 records remain readable. Before restoring a pre-v1.2 evaluator, move imported L3 records to a read-only quarantine ledger and mark every corresponding receipt consumed or revoked so no retained receipt can authorize another operation. Quarantined L3 records remain distinguishable from active L2 decision history.

## Post-rollback verification

Run the complete pre-hardening suite, `sddgov validate`, `doctor`, and CI Cost Guard verification; confirm canonical L0/L1 flows and existing Production gates still behave as documented.
