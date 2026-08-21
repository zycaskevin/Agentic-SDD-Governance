# Fix Scope

## Smallest sufficient change

Add graceful Broker shutdown, publish and verify one complete offline release
bundle, make the benchmark threshold immutable, remove positional redaction
coupling, harden demo cleanup, clarify machine-verifiable key and Evidence
procedures, and add targeted regression coverage. Preserve every authority,
digest, exact-tree, and trusted-Base boundary.

## Files or components in scope

- `src/sddgov/broker.py` and `tests/test_broker.py`.
- `.github/workflows/publish.yml`, `scripts/fresh_wheel_smoke.py`, and release
  workflow contract tests.
- `scripts/benchmark_monorepo_rollback.py` and its tests.
- `src/sddgov/redaction.py`, `tests/test_redaction.py`, and `demo/run.sh`.
- Canonical, packaged, and installed Owner-key/Rollback documents plus release
  notes.
- RC1 Evidence clarification, this review-fix DEP, rollback proof, and rebuilt
  Merge Gate metadata.

## Explicit non-scope

- No TestPyPI/PyPI upload, tag, GitHub Release, environment/ruleset mutation,
  real Owner key, root service installation, or production operation.
- No caller-selected Broker path, mock production Broker, rollback bypass,
  affected-path-only proof, dependency-range change, or weakened test.
- No deletion or rewriting of historical Evidence to manufacture a Gate PASS.

## Blast radius

The service and release paths are security-sensitive and cross-platform, so the
change is L1 and requires full regression proof. The Broker signal handling is
limited to graceful termination; request and ledger semantics remain unchanged.
Offline installation becomes stricter and may expose a missing wheel in the
release bundle rather than reaching a package index, which is intentional.
