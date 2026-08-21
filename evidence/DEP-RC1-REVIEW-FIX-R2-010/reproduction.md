# Reproduction

## Expected

- The root-owned Broker exits through its owned-socket cleanup path on `SIGTERM`
  and `SIGINT`, so a normal service restart cannot be blocked by its stale
  socket.
- The immutable release artifact contains the built distributions, the exact
  runtime lock, an offline dependency wheelhouse, and machine-verifiable
  checksums; fresh-wheel installation uses only that verified set.
- The documented five-second monorepo investigation threshold cannot be
  weakened by a caller-provided CLI value.
- Red Evidence records the command and exit status even when the failing
  command emits no stdout or stderr.
- Key-ceremony fingerprints are generated and checked by machines; witnesses
  verify identity and custody rather than comparing digests.
- Streaming redaction does not depend on tuple position, and both logical-line
  limit paths are covered.
- The onboarding demo checks both required executables and removes its
  temporary directory on interruption.

## Actual

- The Broker installs no signal handler, while its systemd unit stops it with
  `SIGTERM`; Python's default termination bypasses the `finally` cleanup.
- `actions/upload-artifact` uploads only `dist/`, leaving the runtime lock and
  wheelhouse outside the immutable release candidate.
- `--threshold-seconds inf` is accepted and reports no optimization required.
- The original oversized-redaction artifact is zero bytes, so the attachment
  cannot show its generating command or exit status.
- The ceremony asks a witness to compare SHA-256 fingerprints and contains a
  `public_key` placeholder that is not a 32-byte Ed25519 public key.
- Streaming redaction skips `RULES[0]` by position, logical-line rejection has
  no direct regression test, and the demo lacks a `python3` prerequisite check
  and signal cleanup.

## Deterministic steps

1. Inspect `src/sddgov/broker.py` and assert that a `SIGTERM` handler is
   installed before the blocking accept loop; the check exits 1.
2. Parse `.github/workflows/publish.yml`, inspect the upload-artifact path, and
   assert that it includes `requirements-governance.lock`; the check reports
   `artifact_path=dist/` and exits 1.
3. Run `scripts/benchmark_monorepo_rollback.py --file-counts 1 --repeats 1
   --threshold-seconds inf`; the override is accepted and the wrapper exits 1.
4. Measure the shareable oversized-redaction Red log; it is zero bytes.
5. Inspect the ceremony, streaming-rule loop, demo prerequisites, and redaction
   tests using the bounded assertions recorded in `review-red.log`; each exits
   1 for the reviewed Head.
6. Treat the GitHub `pypi` environment configuration finding as a separate
   external release control: it is not satisfiable by changing candidate code.

## Environment and preconditions

- Public PR: `zycaskevin/Agentic-SDD-Governance#23`.
- Commit: `ed2e8a686ff853858f3b45bd5f3db453dc5a8138`.
- Branch: `feat/rc1-readiness`.
- Runtime: Python 3.12.3; Git 2.43.0; Linux aarch64.
- Inputs: committed public source and synthetic fixtures only; no network was
  used for local reproduction.
