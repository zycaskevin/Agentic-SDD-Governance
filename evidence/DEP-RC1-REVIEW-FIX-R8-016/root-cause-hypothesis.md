# Root Cause Hypothesis

## Hypothesis

The R7 candidate protected the primary trust boundaries but several adjacent contracts were checked only at a path, prose, or happy-path level: release inputs were reopened after validation; one listener error escaped the service loop; CI exception arrays admitted ambiguous values; the redactor did not bind the whole Windows path or every partial delimiter; and validation/reporting tests did not assert the earliest safe state transition.

## Supporting evidence

The focused Red suite reproduced the findings independently. In particular, replacing or mutating a release path invalidated the intended validated-input guarantee; a synthetic `accept()` OSError terminated the daemon; a closed DEP attempted to read the caller input first; and proof failures lacked a distinct correctness state. Exact GraphQL review IDs and discussion URLs are preserved in the review-binding artifact.

## Contradicting evidence

Existing R7 Local Green, package, and rollback proofs showed the main RC1 design was viable. The defects were bounded review-hardening gaps rather than evidence of a broken Policy Kernel, signature verifier, exact-tree rollback algorithm, or release version contract.

## Falsification test

Open every external release input once with `O_NOFOLLOW`, hold and `fstat` the descriptor through archive parsing, hashing, and copying, then attempt pathname replacement and in-place mutation. Add deterministic negative tests for every remaining contract and require the focused suite, full Local Green, fresh-wheel proof, and actual rollback drill to pass without weakening exact Base-tree equality.

## Conclusion

Confirmed. Descriptor-bound input operations and post-operation identity checks close the release TOCTOU window; the other findings are closed by exact runtime/schema checks, state ordering, bounded retry/daemon recovery, conservative redaction, and regression contracts. SystemCallFilter remains deliberately deferred until a real target-runtime root rehearsal.
