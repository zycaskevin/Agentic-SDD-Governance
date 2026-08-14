# Reproduction

## Expected

PR #7 should calculate and verify its Merge Gate against the exact current `main` commit while retaining all fail-closed checks.

## Actual

The hosted `verify` job failed before Local Green with `merge gate base_sha does not match the trusted exact base`.

## Deterministic steps

1. Check out the pre-fix PR #7 commit `c305972187250098ca37cfe0524b4a0b34ebca15` with full history.
2. Retain `52ccae6a515fb348e07f19815626b80935eb0608` as the exact trusted Base ref.
3. Do not provision Reviewer key material: PR #7 changes no protected file, and the Base mismatch occurs before protected-file Review is evaluated.
4. Run `sddgov merge verify . --base-ref 52ccae6a515fb348e07f19815626b80935eb0608`.
5. Observe exit code 2 and the exact-base mismatch error.

## Environment and preconditions

The repository still contained `.sddgov/merge-gate.json` from PR #5. The current trusted base is merge commit `52ccae6a515fb348e07f19815626b80935eb0608`; no Production, Secret, Billing, or external runtime is involved.
