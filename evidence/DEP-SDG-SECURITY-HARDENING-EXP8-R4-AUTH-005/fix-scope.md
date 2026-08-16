# Fix Scope

## Smallest sufficient change

Reject a Decision Package before returning successful L2 reuse; keep package validation for genuinely new or reopened decisions.

## Files or components in scope

- `src/sddgov/autonomy.py`
- `tests/test_autonomy.py`
- Changelog and this DEP

## Explicit non-scope

No receipt-format, trust-root, L3 broker, or Production deployment changes.

## Blast radius

Low. Exact L2 reuse without a package continues; ambiguous mixed reuse/escalation requests now fail closed.
