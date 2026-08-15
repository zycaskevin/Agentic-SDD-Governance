# Verification

## Green command and result

The full 188-test suite passes with one sandbox-only AF_UNIX skip; the real AF_UNIX path then passed on this candidate outside the restricted sandbox. `sddgov validate`, CI verify, and strict full/portable DEP checks pass. Fresh wheel installation at `/private/tmp/sdg-exp8-r4-final-wheel-KFPQZs` passed `pip check`, Codex/Hermes setup and doctor with 63 managed files each, and the offline synthetic Muse pilot. Wheel SHA-256: `92335a04ba79bfdfa504675bba2e5d893ca5e1ad95286f7b1f279751de0c81c4`. Sdist SHA-256: `22958ac52f580c76952c100cdf176e43fde4203cc39a505c3a03c94d5b602a32`.

## Before/after evidence

Before: candidate `9978359` ignored the nested Decision Package and reused the receipt. After: the same request returns `BLOCKED existing_decision_reuse_must_not_include_decision_package` before continuation.

## Remaining limitations

This local fix is not an independent approval. A new exact Head still requires P0=0/P1=0 review before receipt, merge, or release.
