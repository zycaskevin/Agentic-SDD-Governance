# Fix Scope

## Smallest sufficient change

Add a closed category-envelope validator before all authorization paths and reject fields belonging to another authority or executor contract.

## Files or components in scope

- `src/sddgov/autonomy.py`
- `tests/test_autonomy.py`
- Experimental.8 DEP and changelog evidence

## Explicit non-scope

No change to Ed25519 receipt verification, L3 nonce consumption, Production deployment policy, or owner trust roots.

## Blast radius

Low. Existing exact L2 and L3 requests remain supported; mixed or unknown authority-bearing request fields now fail closed before reuse.
