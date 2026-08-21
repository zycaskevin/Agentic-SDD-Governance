# Regression Evidence

## Regression test added or strengthened

- `tests/test_redaction.py` proves the 10 MiB fail-fast boundary, 7-byte I/O chunk splitting for provider credentials and multi-line private keys, unterminated-key rejection, and destination-symlink preservation.
- `tests/test_broker.py` proves read-only health, durable ledger initialization, exact record validation, duplicate/corrupt/truncated ledger rejection, one-use nonce consumption, malformed request rejection, non-POSIX failure, and structured readiness output.
- `tests/test_repository_contract.py` binds the 30-second demo, English onboarding parity, protected release inputs, exact-tag OIDC workflow, packaged/installed runbooks, hardened service unit, rollback semantics, and benchmark claim boundary.
- `tests/test_monorepo_benchmark.py` preserves the exact-tree verifier in a small deterministic smoke case; existing Evidence, installer, autonomy, Merge, and pilot suites remain active.

## Related tests executed

- Full Local Green: 247 tests completed successfully; two tests were skipped only because the execution sandbox cannot create the real Unix socket and lacks one historical rollback commit.
- Focused Broker, Redaction, and Evidence suite: 70 tests completed successfully after the final security hardening.
- `sddgov ci local-gate .` ran the declared full unittest suite and repository validation with return code 0 for both commands.
- A clean clone of implementation commit `8b36f52b08a151eaa37fe38ff1cd80856a89a0b2` produced wheel and sdist artifacts that both passed Twine checks and the isolated fresh-wheel smoke.

## Unaffected paths sampled

- Existing L0/L1 classification, signed L2/L3 receipts, fixed-socket client validation, trusted-Base Merge proof, protected review, CI Cost Guard, installer tamper detection, and transactional Evidence tests all remained Green.
- The offline quick demo passed every allow/block/redact/strict-DEP assertion without network, credentials, root, or real data.
- The 1k/10k/50k synthetic benchmark returned exact-tree proof success in every sample; 50k p95 was 0.017217 seconds against the predeclared 5-second investigation threshold, so no affected-path-only optimization was made.
