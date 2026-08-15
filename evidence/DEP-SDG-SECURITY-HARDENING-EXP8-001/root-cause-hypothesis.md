# Root Cause Hypothesis

## Hypothesis

Experimental.7 closes individual leaf and signature checks, but several gates still authorize from a partial representation: caller-declared outer fields instead of an exact action contract, workflow text instead of parsed YAML semantics, final path components instead of retained parent chains, and individually atomic files instead of a recoverable multi-file transaction. These partial representations permit false `CONTINUE`/`PASS`, stale proof publication, blocking non-regular input, or unregistered residue.

## Supporting evidence

- An L1 routine request carrying conflicting authority fields returned `CONTINUE`.
- A generic L2 product receipt was reusable for a forced-human category.
- Comment text and a job-level write override satisfied the CI regex guard.
- Parent replacement, intermediate symlink, and nonblocking requirements were not enforced at the complete path boundary.
- Injected manifest/report failures left unregistered raw/shareable files.
- Attachment publication did not recheck the verified artifact generation and interrupted staging could remain invisible.
- Rollback validation checked only non-empty prose, and the Operational Action queue had no scope/TTL/deduplication contract.

## Contradicting evidence

Experimental.7 already verifies Ed25519 signatures, exact L3 payloads after the L3 branch is reached, final-component `O_NOFOLLOW`, artifact SHA-256 during strict verification, control-generation digests, and no-clobber attachment publication. The defect is incomplete composition and ordering at adjacent boundaries, not absence of all security controls.

## Falsification test

Implement exact per-category request validation, structured L2 reopen semantics, semantic YAML parsing, retained path descriptors, bounded nonblocking opens, artifact-generation recheck, transaction cleanup/recovery, meaningful rollback validation, and durable external-action identity. The hypothesis is falsified only if every new hostile regression becomes Green while existing L0/L1 autonomy, strict Evidence, and L2/L3 tests remain Green.

## Conclusion

Confirmed. The common cause is partial-contract verification across authority, semantic configuration, filesystem generations, and multi-file state transitions.
