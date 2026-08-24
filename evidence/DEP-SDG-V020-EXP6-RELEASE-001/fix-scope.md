# Fix Scope

## Smallest sufficient change

Add this bounded L0 release proof and rebind `.sddgov/merge-gate.json` to the exact current base, reviewed release-preparation Head, change digest, and rollback record.

## Files or components in scope

`.sddgov/merge-gate.json` and `evidence/DEP-SDG-V020-EXP6-RELEASE-001/` only, in addition to the already reviewed Release documentation.

## Explicit non-scope

No changes to Merge verifier code, Workflow logic, protected-file policy, trust stores, Reviewer keys, authority levels, package runtime, repository visibility, Billing, PyPI, or Production.

## Blast radius

Audit metadata for PR #7 and its local release proof only. A mismatch continues to fail closed.
