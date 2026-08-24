# Fix Scope

## Smallest sufficient change

Extract the existing root-owned retained-descriptor reader behind two identity policies: the Agent wrapper remains non-root-only; a new Owner wrapper requires effective UID zero and exactly one of the two fixed public trust paths. Route every Owner card, existing-receipt, pre-sign audience, and final-envelope verification through the Owner wrapper.

## Files or components in scope

- `src/sddgov/trust.py`, `autonomy.py`, and `owner_approval.py`.
- Owner, autonomy, and repository-contract regression tests.
- The governed R22 Decision Contract and request Owner-client binding.
- This supplemental DEP and the RC1 Work Package evidence pointer.

## Explicit non-scope

No private-key access, signer invocation, receipt creation/import, `/etc` mutation, outbox mutation, service change, policy downgrade, production operation, or change to the Agent verifier's root refusal.

## Blast radius

The change affects only public trust-document loading and product-envelope verification routing. Failures remain fail-closed. Reverting the bounded product commit restores the prior R22 preview, which cannot complete root Owner approval and therefore cannot merge.
