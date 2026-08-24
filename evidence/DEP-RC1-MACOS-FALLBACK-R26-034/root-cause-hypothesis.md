# Root Cause Hypothesis

## Hypothesis

The failure is a test-oracle mismatch: the fixture asserts a raw logical path even though the harness intentionally returns the shared canonical fixed-alias path.

## Supporting evidence

The actual and expected paths differ only by the fixed Darwin system alias. The adjacent production-path test already requires canonicalization and the Ubuntu job passes.

## Contradicting evidence

No evidence indicates a production runtime, custody, no-follow, or packaging defect. The failure occurs in the source test assertion before packaging.

## Falsification test

Use the shared canonicalizer for the expected fixture value. The focused fallback test and the adjacent Darwin canonicalization test must both pass without changing production code.

## Conclusion

Confirmed. The test expectation, not the fresh-wheel implementation, used the wrong representation.
