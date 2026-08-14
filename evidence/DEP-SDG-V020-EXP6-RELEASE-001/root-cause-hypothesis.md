# Root Cause Hypothesis

## Hypothesis

The Merge verifier is behaving correctly; the release process omitted the per-PR audit rebind, so PR #7 inherited PR #5's exact base and reviewed Head metadata.

## Supporting evidence

The hosted job reported current base `52ccae6a...`, while the tracked gate records base `849c2bec...`. The failure occurs at the exact-base comparison before tests or package behavior are evaluated.

## Contradicting evidence

The package installs cleanly, all 100 tests pass locally, `doctor` reports no warnings, both strict v1.2 DEPs pass, and the PEP 517 build succeeds. These facts contradict a product-code or dependency failure.

## Falsification test

Regenerate the change digest from current `main`, bind the reviewed non-audit Head, use an L0 release DEP and rollback record, and run the exact verifier. The hypothesis is falsified if the verifier still fails for a reason unrelated to the old base metadata.

## Conclusion

Confirmed. The stale per-PR audit metadata, not the release content or runner environment, caused the failure.
