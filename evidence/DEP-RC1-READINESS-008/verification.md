# Verification

## Green command and result

- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 247 tests Green, two environment-only skips.
- `PYTHONPATH=src python3 -m sddgov.cli ci local-gate .`: unittest and repository validation both returned 0.
- `sddgov validate .`, `sddgov ci verify .`, current-install `sddgov doctor .`, `./demo/run.sh`, and `git diff --check`: PASS; Doctor reports version `0.2.0rc1` and 71 managed files.
- Clean commit build from `8b36f52b08a151eaa37fe38ff1cd80856a89a0b2`: Twine PASS for wheel and sdist. The wheel SHA-256 is `863b350e050f48b777dddf8a6e8f6076c644405282acd90831d06490a251fba7`; the sdist SHA-256 is `9a5d1a10eef5688b8a6bcd35ab86a8b0cf8b762ab2224fafa3b709bcd41c2902`.
- Fresh-wheel smoke installed only the built wheel from an offline hash-locked dependency wheelhouse, reported `source_checkout_imported: false`, passed Codex and Hermes Doctor with 71 managed files each, and passed the synthetic quick demo with `real_data_used: false`.

## Before/after evidence

- Before: a 10 MiB + 1 byte synthetic text source exceeded the five-second reproduction timeout; after: file metadata rejects it before regex processing or output publication, while bounded UTF-8 text streams through 64 KiB reads and keeps logical match state across chunk boundaries.
- Before: `sddgov broker doctor` was not a command; after: it reports five structured checks and remains `NOT_READY` in this unprovisioned environment, as required because no root Runtime Context, external approver store, or trusted Broker service was installed.
- Before: no one-command demo, direct RC path, isolated publish chain, service assets, key/recovery runbooks, or Monorepo measurement existed; after: each has an executable or contract-tested surface and canonical/package/install parity.
- A disposable rollback drill reverted `8b36f52b08a151eaa37fe38ff1cd80856a89a0b2` without conflict, restored the exact Base tree, passed Doctor at `0.2.0-experimental.8` with 66 managed files, and passed all 229 reverted tests with two environment-only skips.

## Remaining limitations

- This is Local Green and release preparation, not proof of TestPyPI, PyPI, GitHub Release, Production Broker, WSL2/macOS host, or real-data deployment.
- GitHub authentication is currently invalid, so Issue/PR creation, push, independent exact-Head review, protected Merge receipt, environment configuration, tag protection, TestPyPI round trip, and public publication remain external gates.
- The recorded artifact hashes identify this local clean-commit build only. The GitHub release workflow must build once from the protected exact version tag, preserve its own immutable artifacts/attestations, and record the registry-round-trip hashes.
- Redaction reduces accidental disclosure but is not legal anonymization; binary Evidence still requires an approved reviewed derivative. The synthetic benchmark validates this harness and environment only, not superiority or universal Monorepo capacity.
