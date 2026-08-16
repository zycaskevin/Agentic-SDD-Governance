# Verification

## Green command and result

Pending the implementation-only commit SHA and final disposable rollback drill.

## Before/after evidence

RED: selected `d7e16f2...` returned a conflict. GREEN will require both the permanent hostile regression and an actual disposable no-commit revert of the rebound commit to pass.

## Remaining limitations

The trusted experimental.7 Base cannot run the new applicability check itself; this bootstrap PR therefore still requires a fresh independent review of the candidate verifier and a real disposable rollback drill before signing.
