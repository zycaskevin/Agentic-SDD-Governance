# Reproduction

## Expected

One exact implementation-only rollback ref must restore the complete candidate's non-Evidence/non-audit tree to trusted Base, not merely undo the newest increment.

## Actual

Reverting `d592892246b1dcfe6cffe50bfd90ea0feeec1227` at the reviewed candidate left the earlier `eb9b64913cf9bbc3fc632a9dce6593c35b8646e3` implementation active and 34 non-Evidence paths different from Base.

## Deterministic steps

1. Use the exact Base and reviewed candidate refs recorded in the red artifact.
2. Apply the selected rollback in a disposable clone.
3. Compare all paths excluding Evidence and Gate/Review audit records against Base.
4. Reconcile installed governance from the reverted source, then run Doctor and the full reverted test suite.

## Environment and preconditions

Trusted Base `a5c27e306373829eee966222c3915f5a822b190c`; reviewed candidate `c3f6ec1d17f3f8313593ef7883d1171942fab7e5`; local disposable clone; no network, credentials, Production state, or user data.
