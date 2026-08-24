# Fix Scope

## Smallest sufficient change

Treat an omitted schema-1.0 Local Green command timeout as the bounded
600-second legacy fallback while retaining explicit template output and strict
validation of configured values. Gate concurrency-group validation on
`require_concurrency`. Apply the computed Monorepo setup timeout to every
fixture Git operation and correct the documentation.

## Files or components in scope

- `src/sddgov/ci_guard.py` and its schema/template documentation mirrors.
- CI Guard, installer-upgrade, and benchmark regression tests.
- `scripts/benchmark_monorepo_rollback.py`.
- Current Work Package provenance and managed manifest hashes.

## Explicit non-scope

- No change to `autonomy.py`, Owner client, trusted approver stores, Decision
  request, or signed receipt.
- No publication, service installation, production action, cost, or credential
  operation.
- No weakening of invalid configured timeout values, non-exempt concurrency,
  exact-tree rollback, or hosted workflow checks.
- The performance-only duplicate trust-domain lookup suggestion is deferred.

## Blast radius

Low and bounded to CI configuration compatibility, workflow exemptions, and
synthetic benchmark setup. The current explicit contract remains byte-stable;
legacy omission becomes bounded rather than unbounded, and protected authority
inputs remain unchanged.
