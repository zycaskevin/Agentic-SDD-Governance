# Root Cause Hypothesis

## Hypothesis

Experimental.8 concentrated on hard authorization and evidence invariants, but its public onboarding and operational control-plane packaging remained release-adjacent documentation rather than executable product surfaces. In the redaction path, retained file descriptors and transactional publication were implemented without a trusted input budget; the implementation accumulates every chunk and applies whole-document regular expressions, so a large regular text file can consume unbounded memory and CPU before any fail-closed result. The L3 path validates a fixed trusted Unix socket but exposes only the client evaluation path, so operators cannot provision or diagnose the separate Broker identity without creating their own undocumented service.

## Supporting evidence

- `src/sddgov/redaction.py` reads 1 MiB chunks into a list, joins all bytes, decodes the entire document, and applies every regex to the complete string without a byte limit.
- The 10 MiB + 1 byte synthetic reproduction exceeded five seconds and was terminated with exit 124 rather than returning a bounded rejection.
- `sddgov broker doctor --json` is not a recognized command and exits 3.
- `src/sddgov/autonomy.py` contains the fixed socket client and trust checks, while the repository contains no Broker daemon entry point or Linux/macOS service asset.
- `src/sddgov/pilot.py` contains a useful offline pilot, but the English README does not expose a one-command demo and is materially shorter than the Traditional Chinese guide.
- `.github/workflows/` contains only the trusted-Base governance verifier; package metadata remains experimental.8 and no separate publishing workflow exists.

## Contradicting evidence

- The pre-change 229-test suite is Green, so existing supported contracts are internally consistent.
- The synthetic Muse pilot already proves several demo ingredients and should be reused rather than replaced.
- Existing L3 unit tests cover socket ownership, parent-chain trust, response fragmentation, and same-UID rejection; the gap is operational packaging and readiness, not absence of client security checks.
- Git tree rollback verification is exact and should not be narrowed merely because a Monorepo performance risk was hypothesized.

## Falsification test

- If bounded redaction still reads or scans beyond the configured maximum, memory/CPU behavior or read-count instrumentation will disprove the fix.
- If a credential or private-key marker split at every possible internal chunk boundary survives redaction, the streaming design is invalid.
- If Broker readiness can mutate nonce state, accept a caller-selected socket, or report ready for an untrusted same-UID socket, the diagnostic design is invalid.
- If the Demo or wheel smoke test requires network, credentials, root, or real data, it does not satisfy the objective.
- If an affected-path optimization is required without a reproducible benchmark threshold, the performance conclusion is unsupported.

## Conclusion

The hypothesis is supported. Implement bounded/stateful processing and executable operational surfaces while preserving existing fail-closed, trusted-Base, retained-descriptor, and exact-tree invariants.
