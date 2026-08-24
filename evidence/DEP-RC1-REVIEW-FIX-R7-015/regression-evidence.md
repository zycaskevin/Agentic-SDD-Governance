# Regression Evidence

## Regression test added or strengthened

New cases pin nonzero pilot exit propagation, 60-second demo subprocess bounds,
literal and escaped Windows plus Unix/macOS path masking across 7-byte chunks,
tracked shareable Evidence inventory, configurable fresh-wheel timeouts, hosted
CI wording, authoritative R7 proof, exact benchmark decisions, release-version
single sourcing, and shared Broker test fakes.

## Related tests executed

- Red: 86 tests, six failures and two errors.
- Intermediate Red: full 297-test suite, one exposed escaped Windows path.
- Local Green: 297 tests executed, 2 explicit sandbox skips, PASS; repository
  validation and the local CI-cost command also passed.
- Packaging: wheel/sdist passed Twine; release bundle bound 10 dependency wheels;
  fresh-wheel installed from a private verified snapshot and passed Codex/Hermes
  Doctor, validation, offline bundle, and synthetic demo checks.
- Rollback: isolated revert of `eb29619f4e9617b5f0e2a67569255e29af92d9ef`
  restored exact Base outside audit paths; 229 Base tests executed with 2 explicit
  sandbox skips, then Base build, Twine, wheel install, CLI and metadata checks
  passed.

## Unaffected paths sampled

The complete suites sample autonomy receipt replay/tampering, symlink/hardlink and
transaction races, trusted-base merge-tree rollback, reviewer key separation,
release OIDC/attestation contracts, L3 readiness, installer parity, monorepo
benchmark safety, and every tracked portable Proof DEP.
