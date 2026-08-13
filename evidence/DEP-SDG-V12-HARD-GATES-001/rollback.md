# Rollback

## Trigger

A Hard Gate authorizes a dangerous action, permits receipt reuse, accepts an invalid signer, or blocks canonical reversible L0/L1 work without a machine-correctable reason.

## Reversible steps

Revert the single bounded Hard Gates commit and restore the previous workflow. Preserve existing v1.2 Production, L2/L3, Redaction, DEP, test, and SHA-256 integrity gates. Remove no user Evidence or state.

## Data compatibility

The change does not mutate Production data. Existing `.sddgov/decisions.json` L2 records remain readable; newly imported L3 records are additive and should be retained as audit history during rollback.

## Post-rollback verification

Run the complete pre-hardening suite, `sddgov validate`, `doctor`, and CI Cost Guard verification; confirm canonical L0/L1 flows and existing Production gates still behave as documented.
