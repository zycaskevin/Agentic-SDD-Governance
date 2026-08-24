# Root Cause Hypothesis

## Hypothesis

The hosted failures are fixture-generation defects: macOS presents fixed system aliases for temporary directories, while the product intentionally compares only canonical physical roots. The local hang is a nested test-lock defect: one unit test uses the production global lock even when its parent process already holds that lock.

## Supporting evidence

- Every systemic macOS authority failure occurs before the test's intended assertion and reports a repository-root mismatch.
- `canonicalize_platform_path` intentionally maps only Darwin `/var`, `/tmp`, and `/etc` aliases to their `/private` targets.
- The affected fixtures store `str(tempfile_path)` directly in synthetic trust-domain rows or mocked Git top-level output.
- The distribution test also builds its synthetic prefix from the same non-canonical tempfile path.
- Host process inspection showed a top-level local-gate process holding `gate-v1.lock` and its complete-suite child blocked in the unit test's nested `run_local_gate` call.

## Contradicting evidence

Linux targeted execution of the three affected modules passed 147 tests with 4 expected skips, showing that the production authority logic and test intent remain sound when logical and canonical paths coincide. This does not contradict the hypothesis; it explains the platform specificity.

## Falsification test

Canonicalize only synthetic fixture roots with the same fixed-alias helper used by production, and give the nested CI guard unit test a private runtime lock root. The hypothesis is falsified if macOS still fails at the root boundary, if intended hostile assertions stop firing, if production trust checks must be weakened, or if a configured Local Green still waits on its own lock.

## Conclusion

Confirmed. Both failures are isolated to test infrastructure. No production trust-domain comparison, root-ownership rule, signer boundary, receipt schema, or approved Owner source input requires modification.
