# Verification

## Green command and result

Preliminary Green passed: `PYTHONPATH=src python3 -m sddgov.cli ci local-gate .` completed 100 tests and repository validation. The exact Merge command will be run after the audit-only gate commit and recorded before the final gate rebind.

## Before/after evidence

Before: hosted Governance run 31818843935 exited 2 at the exact-base comparison. After: the new gate will bind base `52ccae6a...` and the complete experimental.6 release-preparation diff; no acceptance check is removed or skipped.

## Remaining limitations

The GitHub Release assets do not exist until this PR merges. They must be rebuilt from the final `main` commit, uploaded as a pre-release, downloaded again, and machine-verified before Issue #6 is complete.
