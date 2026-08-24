# Fix Scope

## Smallest sufficient change

Add context-bound rollback parsing and Git candidate-range verification; convert rollback records used by experimental.8 to immutable full SHAs; preserve only the exact experimental.7 bootstrap bridge.

## Files or components in scope

- `src/sddgov/merge_gate.py` and rollback/reviewer tests.
- Canonical/package Hard Gates documentation and rollback template.
- Experimental.8 rollback DEP records and the R5 count/scope wording.
- This R6 DEP and Changelog.

## Explicit non-scope

No execution of rollback actions, no Production/Git history mutation, no authority expansion, no Merge/Release, and no unrelated P2 review cleanup.

## Blast radius

Medium and security-critical but bounded to Merge rollback validation. Existing v2 plans must be migrated to full SHAs; the selected v1 path remains compatible with the old trusted Base.
