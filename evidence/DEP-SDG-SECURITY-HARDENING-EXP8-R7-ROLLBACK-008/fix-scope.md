# Fix Scope

## Smallest sufficient change

Add a non-executing conflict check to Merge verification and establish a clean implementation-only commit followed by Evidence binding. Rebind every experimental.8 rollback record to that commit.

## Files or components in scope

`src/sddgov/merge_gate.py`, rollback tests, canonical and packaged Hard Gates docs, CHANGELOG, experimental.8 Evidence records, and Git commit boundaries.

## Explicit non-scope

No authority model, Production deployment, Secret handling, dependency policy, public release, or unrelated P2 finding.

## Blast radius

L1 local Git/release-engineering behavior. The verifier reads Git objects and creates only an unreferenced merge-result tree object; it does not change the worktree or execute hooks, shell text, tests, or network access.
