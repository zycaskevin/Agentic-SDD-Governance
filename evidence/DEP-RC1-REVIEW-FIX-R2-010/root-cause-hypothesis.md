# Root Cause Hypothesis

## Hypothesis

The first RC1 readiness pass verified each feature's primary success and
fail-closed path but did not model the complete operational handoff boundary:
service-manager termination, immutable release-bundle contents, fixed benchmark
policy, and human-versus-machine ceremony responsibilities. Small positional and
shell assumptions were likewise not represented by regression tests.

## Supporting evidence

- The Broker has a cleanup `finally` block but installs no handler for the
  service unit's default `SIGTERM`.
- The build job creates a wheelhouse and uses it for one smoke test, while the
  uploaded artifact path is only `dist/`.
- The documented five-second threshold is a public CLI argument and accepts
  non-finite values.
- The separate Red context artifact records exit 124, but the attachment does
  not explain that the command's stdout/stderr artifact is intentionally empty.
- The key runbook explicitly asks a witness to compare fingerprints, and its
  JSON example contains a non-decodable placeholder.
- The streaming implementation uses `RULES[1:]`; the demo and logical-line
  negative paths lack direct tests.

## Contradicting evidence

- The Broker ledger, request framing, one-use nonce, readiness checks, and
  fixed-path authority boundaries remain covered and were not implicated.
- The release workflow already builds once, pins Actions, uses hash-locked tool
  installation, OIDC, attestations, and an exact immutable tag.
- The rollback verifier already rejects a reverted descendant because its Head
  no longer equals the Gate-bound reviewed Head; historical DEP files are not a
  reusable active approval.

## Falsification test

Add focused tests that simulate service-manager termination and restart, verify
an exact release-bundle inventory and offline hash-locked install, reject the
threshold override, cover both logical-line flush paths, and assert the demo and
ceremony contracts. Revert the implementation commit in a disposable clone and
confirm the old Merge Gate exits nonzero for a Head mismatch.

## Conclusion

Confirmed. The defects share an incomplete boundary-test cause rather than a
failure of the underlying trusted-Base, signature, nonce, or exact-tree design.
The GitHub `pypi` environment itself remains an external control-plane action,
not a candidate-code defect.
