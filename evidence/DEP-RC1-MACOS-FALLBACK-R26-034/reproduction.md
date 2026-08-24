# Reproduction

## Expected

The fallback smoke workspace test compares the workspace parent using the same fixed-alias canonical representation as the production harness.

## Actual

PR #51 R25 failed one hosted macOS source-Green test before package construction. The harness returned a canonical Darwin system path while the assertion retained the logical alias spelling.

## Deterministic steps

1. Run the complete source suite on the hosted macOS 15 runner at the R25 Gate.
2. Observe the single failure in `test_fresh_smoke_workspace_falls_back_when_tmp_is_unavailable`.
3. Compare the fallback fixture path with `canonicalize_platform_path(fallback)` and observe equality with the workspace parent.

## Environment and preconditions

The runner must be Darwin, where a fixed operating-system alias can resolve to its canonical private target. No arbitrary symlink following is involved.
