# Root Cause Hypothesis

## Hypothesis

Two independent contract gaps caused the rejection. First, the prior reconstruction replayed historical Merge Gate commits before reviewed Head; although the candidate verifier allowed those audit paths, the trusted Base verifier did not, so the candidate attempted to authorize its own relaxed rollback topology. Second, the publish workflow separated release tools from its isolated governance test environment without accounting for complete test discovery importing release-helper modules.

## Supporting evidence

The independent review transcript records that rollback v3 parsing, commit range, and Change Digest all pass while Base `_rollback_ref_is_cleanly_revertible` returns false. Listing commits between R12's rollback ref and reviewed Head shows `.sddgov/merge-gate.json` changes. The isolated-venv transcript reaches 340 tests and then raises `ModuleNotFoundError: packaging`; adding the hash-locked release requirements makes all 357 tests pass.

## Contradicting evidence

R12 current-code tests, DEP verification, Local Green, package proof, and an actual exact-tree revert drill otherwise passed. This does not justify changing trusted Base, expanding its audit allowance, weakening the receipt requirement, force-pushing PR #34, or moving release dependencies into the runtime package. The problem is bounded to candidate topology and the workflow test environment.

## Falsification test

The hypothesis is falsified if any non-`evidence/**` path appears in `096624a..reviewed_head`, if the exact Base verifier rejects the rebuilt rollback topology for a reason other than the deliberately absent independent receipt, or if a fresh environment with both lock files still fails complete test discovery. Structural tests must also prove both lock installs precede the full suite in the isolated workflow step.

## Conclusion

Confirmed. The candidate is reconstructed with product commit `096624a529dea88d091777c8012bbdba3346cdbe` directly above Base, and every descendant through the exercised Evidence Head changes only `evidence/**`. The release workflow and repository contract require both hash-locked environments before complete test discovery. The complete current Green matrix and actual trusted-Base rollback drill pass; the final Merge Gate must still be checked by the exact Base verifier and independently signed.
