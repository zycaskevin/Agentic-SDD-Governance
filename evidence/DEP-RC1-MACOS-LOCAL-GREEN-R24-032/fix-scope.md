# Fix Scope

## Smallest sufficient change

Canonicalize synthetic temporary repository roots in autonomy, Broker, and Owner approval tests before storing or comparing them. Give the CI guard test that calls `run_local_gate` its own retained temporary lock base, matching the isolation already used by adjacent tests.

## Files or components in scope

- `tests/test_autonomy.py`
- `tests/test_broker.py`
- `tests/test_owner_approval.py`
- `tests/test_ci_guard.py`
- This R24 DEP and the final Gate metadata.

## Explicit non-scope

No production source change, trust-store change, Owner-client digest change, request/Decision Contract change, receipt recreation, signer access, private-key access, policy downgrade, or hosted workflow relaxation.

## Blast radius

Only test fixture paths and the unit-test lock namespace change. Reverting the final immutable product commit returns to trusted Base and removes the entire RC1 candidate, including the already approved public decision row; no external trust data or Owner receipt is deleted.
