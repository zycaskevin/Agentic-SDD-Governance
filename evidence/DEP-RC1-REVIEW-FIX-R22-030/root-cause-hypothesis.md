# Root Cause Hypothesis

## Hypothesis

R21 implemented several local cleanup helpers but did not define one outer commit boundary spanning all retained path leases, publications, predecessor claims, descriptor closes, and durability steps. Several callers therefore inferred commit state from a publication list or pathname observation. Separately, the authority-path change was treated as a routine fix even though it changed a trusted-Base public authority-source contract, and the receipt contract exposed machine signing mechanics directly to the Owner instead of separating the non-signing Agent card from an Owner-controlled signer client.

## Supporting evidence

- Independent reproductions reached the specific failure windows without modifying unrelated product behavior.
- Public generation identity alone was insufficient where same-inode bytes or predecessor claims could change.
- Caller catch blocks returned success solely because a publication identity had been appended, before the outer lease finalized.
- Release cleanup used a complete expected payload while the owned file could contain only a verified prefix.
- The trusted Base explicitly permits an externally selected root-owned approver store, while R22 retires that selector and fixes the authority source.
- `sddgov` could classify and import a product decision but had no command that rendered the exact governed request without signing, while the runbook left receipt construction and signature handling to a human.

## Contradicting evidence

Normal success-path unit tests, source validation, package build, and exact-tree rollback remained Green. These results contradict a broad product failure but do not falsify the narrower transaction and authority-boundary hypothesis because they do not force the hostile linearization points.

## Falsification test

Add failure injection at every precommit close/publication/lease/finalizer boundary; mutate or replace generations at cleanup; force partial writes; exercise fixed Darwin system aliases; require an exact signed L2 decision row in the repository contract; and prove that the Agent CLI has no signing command while a separate Owner CLI renders one A/B card, accepts no private-key/signature argument, signs only through one matching external identity, and creates no receipt on refusal or verification failure. The hypothesis is falsified if these tests pass without an outer transaction, complete snapshot validation, separated signer path, or Owner receipt.

## Conclusion

Confirmed. The failures share an incomplete transaction/authority-boundary model, not an unrelated packaging or algorithm defect.
