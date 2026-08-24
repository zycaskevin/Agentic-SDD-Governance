# Fix Scope

## Smallest sufficient change

Canonicalize the fallback fixture's expected parent with the existing shared platform canonicalizer.

## Files or components in scope

`tests/test_release_bundle.py`, the authoritative work-package provenance, its repository contract, and this R26 Evidence package.

## Explicit non-scope

No production path logic, Owner client source, trust store, signer, receipt, package runtime, or operating-system permission contract changes.

## Blast radius

Test-only behavioral scope. The only product-tree behavior change is a cross-platform assertion that now matches the established harness contract.
