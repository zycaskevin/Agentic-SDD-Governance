# Verification

## Green command and result

Green passed: `PYTHONPATH=src python3 -m sddgov.cli merge verify . --base-ref 52ccae6a515fb348e07f19815626b80935eb0608` returned `MERGE_READY`, verified this strict DEP and rollback record, and completed 100 tests plus repository validation.

## Before/after evidence

Before: hosted Governance run 31818843935 exited 2 at the exact-base comparison. After: local exact verification bound base `52ccae6a...`, reviewed non-audit Head `1304fd4...`, and the complete experimental.6 release-preparation digest; no acceptance check was removed or skipped.

## Remaining limitations

The GitHub Release assets do not exist until this PR merges. They must be rebuilt from the final `main` commit, uploaded as a pre-release, downloaded again, and machine-verified before Issue #6 is complete.
