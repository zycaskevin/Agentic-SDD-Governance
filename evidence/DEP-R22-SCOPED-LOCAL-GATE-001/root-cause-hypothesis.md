# Root Cause Hypothesis

## Hypothesis

The Local Green contract models R22 as unconditional even though its authority
scope is narrower; no exact, fail-closed path classifier existed.

## Supporting evidence

The current contract lists `decision verify-product` as an unconditional local
command. The targeted regression suite proves that the new offline classifier
protects authority-bearing inputs and refuses ambiguous path data.

## Contradicting evidence

No contradictory result was found in the focused CI Guard and repository
contract suites.

## Falsification test

If an R22 authority input or the Gate configuration were classified as
unrelated, the hypothesis would be false. The targeted tests assert the
opposite.

## Conclusion

Confirmed for the offline foundation. The classifier is not enabled, so this
does not yet change Local Green behavior.
