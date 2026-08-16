# Reproduction

## Expected

A declared rollback must restore the exact non-Evidence Base tree and leave the installed Agent governance healthy under `sddgov doctor`. A Work Package with `max_runs_per_work_package: 1` must have one automatic hosted verification path.

## Actual

Reverting PR #14 implementation commit `fd691a7a069fbaa0f5d5f17886524a29f1ba17a4` at reviewed Head `3dfd3061bb3bd58b40a3877039a87c45bdd9d943` restores the non-Evidence tree to Base `6a90ad84e8ed141241d3ca972b5ab91251429671`, but Doctor exits 1 because `.sddgov/project.json` remains experimental.8 while the installed manifest returns to experimental.7. GitHub also records two successful hosted runs for the Work Package.

## Deterministic steps

1. Clone the repository into a new temporary directory and check out `3dfd3061bb3bd58b40a3877039a87c45bdd9d943`.
2. Run `PYTHONPATH=src python3 -m sddgov.cli doctor .`; confirm it succeeds.
3. Run `git -c core.hooksPath=/dev/null revert --no-commit fd691a7a069fbaa0f5d5f17886524a29f1ba17a4`.
4. Compare the non-Evidence/non-audit tree with Base `6a90ad84e8ed141241d3ca972b5ab91251429671`; confirm it matches.
5. Run Doctor again; confirm exit 1 and `.sddgov version does not match install manifest`.
6. Read GitHub run metadata for `31931408005` and `31931428520`; confirm the first is `pull_request_target` and the second is `push`, both successful.
7. Require the observed count of two to exceed `.sddgov/ci-cost-guard.json` value `max_runs_per_work_package: 1`; fail the reproduction otherwise.

## Environment and preconditions

Public repository; exact immutable Git commits; clean temporary clone; Python 3; no Production data, credentials, Secrets, or raw user data. The captured artifact contains public commit and Actions identifiers only.
