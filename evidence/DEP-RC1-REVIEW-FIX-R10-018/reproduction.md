# Reproduction

## Expected

Every still-valid PR #31 finding is independently reproduced and fixed without weakening fail-closed controls. A new JSON artifact has accurate media metadata, historical proof remains readable by the trusted Base after rollback, release jobs cannot silently skip, and the L3 Broker cannot allocate or retry indefinitely.

## Actual

The exact CodeRabbit review of commit `d0675e6bebed0cc89c978a251ca321365a2a571d` reported 10 inline findings, one outside-diff finding, and 11 minor findings. The 89-test focused Red run recorded six failures and three errors. An initial rollback drill then showed that retroactively relabeling R6-R9 JSON rows made trusted-Base strict verification fail; a current Local Green run also rejected the reverted historical labels until the manifest contract was explicitly versioned.

## Deterministic steps

1. Start from the exact reviewed R9 Head `d0675e6bebed0cc89c978a251ca321365a2a571d` and apply only the R10 regression assertions.
2. Run the focused 89-test command preserved in `terminal--r10-red-tests.txt`; observe exit 1 with six failures and three errors covering permanent-403 retry, unbounded report probing, JSON media type, Broker ledger iteration/logging/retry, and related contracts.
3. Rehearse `git revert --no-commit` of the first R10 atomic candidate while retaining audit-only R6-R9 descendants; observe trusted-Base strict verification reject the retroactively changed historical media labels in `terminal--r10-rollback-compat-red.txt`.
4. Restore the legacy labels without a version bridge and run Local Green; observe current strict verification reject those same labels in `terminal--r10-legacy-media-red.txt`.
5. Use `git--r10-review-bindings.txt` to bind each review ID and verified disposition rather than relying on prose-only review state.

## Environment and preconditions

Trusted Base is `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. The review is PR #31 formal review `4996217667` at the exact R9 Head above. Inputs are synthetic or repository metadata only; no real credential, private key, patient/customer data, production action, privileged Broker installation, or package publication is used.
