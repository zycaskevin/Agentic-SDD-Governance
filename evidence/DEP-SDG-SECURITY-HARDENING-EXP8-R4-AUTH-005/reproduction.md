# Reproduction

## Expected

An existing exact L2 product decision is reused only with its decision ID and scope, without any new package or foreign authority data.

## Actual

The reuse path accepted an allowed top-level `decision_package` object containing a nested L3 operation field and returned `CONTINUE` without validating the package.

## Deterministic steps

1. Import a valid signed L2 product receipt.
2. Submit the exact decision ID and scope plus a `decision_package` containing one unknown structured authority field.
3. Observe `CONTINUE existing_decision_reused_without_duplicate_question` at candidate `9978359`.

## Environment and preconditions

Fresh PR #12 checkout; synthetic keys, receipt, and operation payload only.
