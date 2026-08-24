# Regression Evidence

## Regression test added or strengthened

- Legacy schema `1.0` omission passes verification and the runtime receives the
  bounded 600-second fallback.
- Explicit custom timeout survives `setup-agent --force`; invalid configured
  values remain rejected.
- Exempt workflows skip concurrency-group validation while non-exempt workflows
  retain the non-empty group requirement.
- A mocked large fixture asserts that every benchmark `_git` call receives the
  scaled setup timeout.
- Repository contract binds the authoritative R28 DEP.

## Related tests executed

- Four exact R28 regression tests: PASS.
- `tests.test_ci_guard` plus `tests.test_monorepo_benchmark`: 46 PASS.
- Complete source suite: 532 PASS, including 14 expected platform/sandbox
  skips.
- `sddgov validate .`: PASS.
- `sddgov ci verify .`: PASS.
- Candidate wheel and sdist build plus Twine metadata checks: PASS.
- Hash-locked offline bundle: PASS with 10 dependency wheels and 4 public
  release assets.
- Fresh installed-wheel smoke: PASS without importing the source checkout;
  Codex and Hermes each validated 73 managed files, the offline bundle was
  verified, the quick demo passed, and the real Linux AF_UNIX Broker suite
  passed.
- Trust-bound Local Green: PASS in the fixed repository audience. It ran all
  532 tests with 5 expected platform skips, source validation, and the exact
  Owner-signed product-decision verifier under a 600-second per-command bound.
- Declarative rollback rehearsal: reverting the immutable R28 product commit
  restored the exact trusted-Base non-audit tree. Reconciliation setup, Doctor,
  validation, 237 Base tests with 1 expected sandbox skip, Base build/Twine,
  hash-locked dependency install, `pip check`, and a fresh installed-wheel
  setup/Doctor consumer all passed.

## Unaffected paths sampled

- Owner-client source identity remains
  `2bd8ea9fdeec596feb0997f36ddb0f189394e7fa392a64b6a19bb4d06fd997d2`.
- Exact Decision and request artifact hashes remain unchanged.
- Hosted workflow semantics, Owner approval, Broker, Evidence, Redaction,
  release, rollback, and repository-contract suites remain Green.
