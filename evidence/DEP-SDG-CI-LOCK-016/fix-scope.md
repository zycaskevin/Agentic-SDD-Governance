# Fix Scope

## Smallest sufficient change

Create one persistent owner-only POSIX lock record under the canonical system
temporary directory, namespaced by current numeric UID. Open it with no-follow
and close-on-exec flags, validate directory/file ownership, type, mode, link
count, and identity, acquire an exclusive advisory lock, then wrap the complete
`run_local_gate` operation.

## Files or components in scope

- `src/sddgov/ci_guard.py`
- `tests/test_ci_guard_lock.py` and existing CI Guard tests
- `docs/CI_COST_GUARD.md` plus its managed copies/resources
- WP, Issue, and L1 DEP

## Explicit non-scope

- No command, environment, timeout, acceptance criterion, or retry change.
- No repository-derived lock name or content.
- No hosted CI, merge authority, Reviewer trust, Vault runner/verifier, HOME,
  push, release, installation, or live action.

## Blast radius

Local Green invocations for the same POSIX user become sequential. Concurrent
jobs may wait longer, but command results and ordering within each gate remain
unchanged. A process exit releases the advisory lock. Direct commands that do
not use `sddgov ci local-gate` remain outside this coordination boundary.
