# Root Cause Hypothesis

## Hypothesis

The security claims fail when verifier, Owner authority, freshness, one-use state, content classification, or Evidence completeness can be selected or asserted by the same Agent being governed rather than independently recalculated or enforced by a separate control plane.

## Supporting evidence

- The workflow checks out and installs the PR head before invoking the Merge verifier.
- Strict DEP verification did not require every raw row to be represented in the Redaction Report, and label/suffix-controlled `.bin`/HAR routes bypassed intended content rules.
- DEP creation accepts an unsanitized caller-provided ID; collection and redaction permit existing per-file links or names.
- Same-UID `0600` files and caller-selected commits were accepted as Owner authority; L2 freshness trusted caller-provided digests/booleans.
- L3 local state could be replayed in another clone, signed runtime labels were not compared with a separate execution context, and malformed Base Reviewer state could fall back to bootstrap authority.

## Contradicting evidence

The existing implementation already rejected unknown categories, detected protected-path changes, bound most signed fields, and blocked several top-level link attacks. These controls show the failure is bounded to missing independent trust/freshness/nonce boundaries and incomplete per-artifact contracts rather than a total absence of fail-closed behavior.

## Falsification test

Load the verifier from an immutable base checkout; replay every independent Reviewer exploit; then require exact artifact relationships, no-follow reads, separate-identity Owner trust, byte-derived L2 freshness, complete L3 payloads, an external atomic nonce ledger, and Base-authoritative revocation. The hypothesis is falsified if any exploit still reaches `PASS`/`CONTINUE` or normal L0/L1 work stops.

## Conclusion

Confirmed. Independent synthetic reproduction and source inspection agree on the same missing trust bindings.
