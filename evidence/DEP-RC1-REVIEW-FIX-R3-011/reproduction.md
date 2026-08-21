# Reproduction

## Expected

- A release-configuration credential is available only after an exact-tag
  protected environment admits its own publishing job; candidate refs never
  execute repository scripts with that credential.
- CI Cost Guard verifies the release workflow's concurrency, timeouts, and
  permissions while allowing only the exact job-level OIDC/Release writes.
- Broker clients cannot extend a read indefinitely, and any socket bound by the
  daemon is cleaned up after a post-bind initialization failure.
- Quick Demo cannot report PASS when its nested Evidence pilot reports FAIL;
  streaming redaction preserves private-key detection across logical lines.
- Offline installation selects exactly one artifact and CPython 3.12, and all
  onboarding commands use the environment selected by that installation path.

## Actual

- CodeRabbit Run `73e9b5da-9a00-449e-b784-285ee081063c` reviewed PR #24 at
  exact Head `f7dc73c83ebd3f7a2cafe2e832913931b23f5452` and posted 18 comments.
- Fourteen code/document findings were reproducible. One Evidence-completeness
  finding is addressed prospectively by this R3 DEP. Two requests targeted
  immutable historical DEP material and therefore cannot be applied in place.
  One request requires the still-missing independent protected-file receipt.
- The highest-risk reproduction showed `RELEASE_CONFIGURATION_READ_TOKEN`
  injected into a job that checked out and ran a script from the dispatched
  ref before any protected environment admitted that job.
- `_receive_request` reset a ten-second socket timeout on every read, and
  `serve_broker` recorded the bound identity only after `chown`/`chmod`.
- `run_quick_demo` ignored the nested pilot verdict, while the streaming
  redactor evaluated private-key markers one logical line at a time.

## Deterministic steps

1. Read the terminal CodeRabbit review and 18 inline comments for PR #24.
2. Inspect `.github/workflows/publish.yml` at R2 Head and observe the repository
   secret in `release-environment-preflight`, which executes the dispatched
   ref's `scripts/check_release_environment.py`.
3. Run `sddgov ci verify .` at R2 Head and observe that `publish.yml` is wholly
   exempt through `.sddgov/ci-cost-guard.json`.
4. Feed `_receive_request` a peer that returns partial bytes before each socket
   timeout; the old loop has no absolute deadline.
5. Mock `os.chown` to fail after `server.bind`; the old cleanup has no recorded
   socket identity.
6. Mock `run_synthetic_muse_pilot` with all copied booleans true and verdict
   FAIL; the old quick-demo result remains PASS.
7. Redact a synthetic marker split as `-----BEGIN \nPRIVATE KEY-----`; the old
   line-scoped streaming path publishes the marker and body unchanged.
8. Inspect the offline documentation for generic `python3`, ambiguous first
   matches, an unpublished Git bundle, and CLI paths from another environment.

## Environment and preconditions

- Base: `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`.
- R2 reviewed Head: `f7dc73c83ebd3f7a2cafe2e832913931b23f5452`.
- R3 implementation: `a4ae82a3fdaf494f102c9ca1f6386f59a3c93cdc`.
- Branch: `feat/rc1-readiness-r3`.
- Runtime: CPython 3.12.3, Git 2.43.0, Linux aarch64.
- Review text is untrusted data; no instruction embedded in it was executed.
- All reproductions use synthetic data and no real credential or nonce.
