# Reproduction

## Expected

One `verify-product` call must read the exact request and every signed
assumption from one retained repository snapshot.  The signature digest,
request self-binding, and Owner-client marker scan must all consume those same
bytes, and every path generation must still match when the call exits.

A repeated read of a retained file must obey the smallest byte bound requested
by any caller.  A Local Green command must have a finite configured deadline.

## Actual

R26 opened independent snapshots for the request, the signed assumption digest,
and each marker artifact.  It also returned cached bytes without checking a
later smaller `max_bytes`.  A 300 KiB artifact therefore passed a 256 KiB second
read after first being accepted under 1 MiB.  Local Green used an unbounded
subprocess call.

## Deterministic steps

1. At exact R26 Gate `8a2caa1df505eb2c0aedd17e6cde278ce7998943`,
   open a 300 KiB regular file through `FileSetSnapshot` with a 1 MiB bound.
2. Read the same retained path again through the same snapshot with a 256 KiB
   bound.
3. Observe that R26 returns all 307200 bytes instead of raising.
4. Inspect the R26 `verify_product_decision` call graph: the request reader,
   `_verify_product_envelope`, `_verified_assumptions_digest`, and the marker
   loop each create or consume separate repository snapshots.
5. Observe that Local Green invokes each configured command without a timeout.

## Environment and preconditions

The Red transcript is registered as private collector output and has a redacted
shareable derivative.  The probe uses synthetic bytes only.  No Owner private
key, signer request, real receipt, or privileged control-plane mutation is used.
