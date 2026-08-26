# Root Cause Hypothesis

## Hypothesis

The new decision document omitted the canonical Owner-client marker required by
`build_product_approval_card`.

## Supporting evidence

The exact committed marker count was zero; the verifier requires exactly one.

## Contradicting evidence

Trust-file readability and signer-socket preflight completed in the Owner
terminal, but the generic error intentionally did not disclose an internal stage.

## Falsification test

Add exactly one canonical marker and run a decision-specific count assertion
plus the existing generic Owner-client identity test.

## Conclusion

Confirmed. Both tests pass after the one-line marker correction.
