# Reproduction

## Expected

Every release failure written to stdout or a shareable JSON report must remove
the bare host home/temporary roots and complete descendant paths, including
paths containing spaces. Report publication must not follow symlinks or replace
an existing filesystem object. The current DEP and Gate must match the Work
Package's L1 classification; predecessor Evidence remains immutable.

## Actual

The PR #38 independent reviewer reproduced the bare host home in public error
text and a residual `Build/input.whl` suffix for a space-containing path.
`prepare_release_bundle.py` created report parents and wrote the report through
pathname APIs, so an existing report symlink redirected the write. A compressed
archive `zlib.error` escaped the sanitized failure boundary. The WP was L1 while
R14-R16 DEP/Gate metadata was L2 and the decision store was empty.

## Deterministic steps

1. Call both release `_public_error` functions with the bare home path and with
   a home-relative `Sensitive Build/input.whl`; observe host path disclosure or
   a residual suffix on R16.
2. Point `--report`/`--output` at a symlink to a sentinel regular file; observe
   the R16 pathname writer overwrite the target.
3. Raise `zlib.error` from bundle preparation; observe it bypass the R16 public
   JSON error handler.
4. Compare the L1 Risk line in `WP-RC1-READINESS-008.md` with the R16 L2
   `summary.yaml` and `.sddgov/merge-gate.json`; confirm decisions are empty.

## Environment and preconditions

Red is exact PR #38 Gate Head `addd5aa682696be6514df0c76f6cf835e58b4c9c`
against Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. Green begins at
single-parent R17 atomic product commit
`b827040cb8d8315cfd93afb309e4f9bf579775c9`. All paths in tracked Evidence are
synthetic placeholders; no private key, customer, patient, payment, or real
production data is used.
