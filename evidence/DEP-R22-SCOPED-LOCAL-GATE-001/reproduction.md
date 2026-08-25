# Reproduction

## Expected

The existing unconditional R22 command blocks AF27 although AF27 does not
change Owner authority or its verifier. A replacement classifier must never
skip R22 when the change set is absent, malformed, or touches protected scope.

## Actual

The current Local Green contract executes R22 for every change. The new
offline classifier distinguishes the synthetic AF27-only path set while
retaining fail-closed behavior for unknown and protected inputs.

## Deterministic steps

1. Run `python -m unittest tests.test_r22_scope tests.test_ci_guard tests.test_repository_contract -v` with `PYTHONPATH=src`.
2. Confirm that empty, malformed, Gate-config, Owner-client, decision, and
   packaged-resource paths require R22.
3. Confirm that only the exact AF27 fixture does not require R22.

## Environment and preconditions

Offline synthetic paths only. No Owner key, receipt, control-plane file,
network call, production operation, or Gate configuration mutation is used.
