# Fix Scope

## Smallest sufficient change

Remove the ancestry-only filter; make every Evidence read ceiling mandatory; introduce one shared descriptor-bound new-file primitive for Pilot outputs; extend deterministic local-path masking; publish stable benchmark error categories; strengthen recovery and user documentation; and register forward-only withdrawals and corrections for affected predecessor proof.

## Files or components in scope

`merge_gate.py`, `evidence.py`, `fs_security.py`, `pilot.py`, `redaction.py`, release/native smoke helpers, the Monorepo benchmark, canonical and mirrored rollback documentation, the Traditional Chinese guide, repository tests, the RC1 Work Package, and R18 Evidence metadata.

## Explicit non-scope

No runtime authorization class changes, no real L3 operation, no release publication, no Owner/reviewer key change, no protected-branch ruleset change, no affected-path rollback optimization, and no modification or deletion of R6-R17 Evidence.

## Blast radius

The Gate traversal and Evidence reader are security-critical and fail closed. Pilot output now rejects pre-existing destinations. The broader path rule withdraws previously accepted local-path artifacts, recorded explicitly rather than hidden. Packaging and installed Governance mirrors must remain byte-identical.
