# Root Cause Hypothesis

## Hypothesis

R19 closed individual path and publication cases but did not model the complete representation/transaction boundaries: the regex modeled slash-form UNC only, the redactor reconciled only the current source, Evidence duplicated a partial Darwin normalizer, and the native/package workflow treated parallel or later verification as equivalent to validation-before-build.

## Supporting evidence

The independent reviewer reproduced every boundary on the exact R19 Head. Focused R20 tests fail if native UNC alternatives are removed, if call-wide publication tracking is reduced to per-source state, if Evidence stops using the shared alias normalizer, or if build moves before source Green.

## Contradicting evidence

R19 still passed 403 tests, package smoke, real Linux sockets, and hosted native jobs. Those results contradict a broad implementation failure and localize the defect to missing boundary cases and ordering.

## Falsification test

Run the new regressions against the corrected implementation, mutate each guard back to the R19 behavior, and confirm the relevant test fails while the unaffected suites remain Green.

## Conclusion

Confirmed. The smallest sufficient fix is shared representation handling, one outer redaction transaction, ordered source verification, concurrent pipe draining, explicit interpreter selection, and exact contract-test cleanup.
