# Reproduction

## Expected

A valid L2 product receipt authorizes only the exact bounded product decision fields that were signed and recorded.

## Actual

The same valid L2 decision was reused when the request also contained a foreign L3 operation payload, and the classifier returned `CONTINUE`.

## Deterministic steps

1. Import a valid signed L2 product-decision receipt.
2. Build an L2 `product_decision` request with the exact decision ID and scope.
3. Add one foreign field such as `operation_payload`, `approval_id`, `operation_id`, `target`, `parameters`, or nested authority data.
4. Evaluate escalation at candidate `d03213a` and observe decision reuse instead of a fail-closed result.

## Environment and preconditions

Fresh checkout of PR #12 exact candidate `d03213a62abb1d5752eea3380d3f75275e069dbf`; synthetic keys and payloads only; no Production authority or credentials.
