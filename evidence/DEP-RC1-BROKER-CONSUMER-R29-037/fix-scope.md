# Fix Scope

## Smallest sufficient change

Make the consuming client use the same fixed platform group name as the Broker,
resolve it before connecting, require root UID, exact GID, exact mode `0660`,
and AF_UNIX socket type, and fail closed when platform/group lookup is
unsupported. Add deterministic negative regressions. Apply the two bounded
test-only cleanups from the same exact CodeRabbit review.

## Files or components in scope

`src/sddgov/autonomy.py`, the shared Broker group constant in
`src/sddgov/broker.py`, `tests/test_autonomy.py`,
`tests/test_owner_approval.py`, the current Work Package, Owner-client binding,
and this authoritative DEP.

## Explicit non-scope

No Broker path override, no permission relaxation, no service installation, no
nonce consumption, no private-key access, and no Production operation. The
approved fixed authority contract is unchanged.

## Blast radius

The security check runs immediately before the AF_UNIX client connection. Since
`autonomy.py` is part of the signed Owner-client identity, the exact Decision
assumption binding and receipt must be regenerated before final Green.
