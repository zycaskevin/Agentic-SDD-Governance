# Reproduction

## Expected

Every release input and output must remain bound to validated ancestor-directory and file descriptors through enumeration, hashing, copying, and archive generation. Evidence collection must reject an oversized source before publication or unbounded buffering. CI, benchmark, documentation, service-mirror, cleanup, and fresh-wheel contracts must fail closed at their exact boundary.

## Actual

The commit-bound CodeRabbit review on PR #30 identified nine inline findings, one outside-diff CI finding, and bounded maintainability/security nitpicks. The focused Red command ran 11 tests and produced nine failure records plus three errors, including subtest failures, across ancestor-directory binding, pre-buffer Evidence limits, missing-workflow permission exceptions, retry/slug validation, nested wheel paths, fresh-smoke report creation, benchmark schema/timeout, English README parity, and rollback-runbook fetch ordering.

## Deterministic steps

1. Start from the exact reviewed R8 product Head `115113691d814236df33571475bb8f519fd65b23`, then apply only the new R9 regression assertions as uncommitted test changes. Commit `5120d60ab018edfee75f38c80d4e3abe872d1725` is an audit-only descendant used later for rollback topology; it is not described as a pre-fix product tree.
2. Run the exact 11-test unittest command preserved in `terminal--r9-red-tests.txt`.
3. Observe command exit 1 with nine failure records and three errors.
4. Map every record to the exact PR #30 review IDs preserved in `git--r9-review-bindings.txt`; do not treat the missing independent reviewer receipt as an implementation defect or self-approve it.

## Environment and preconditions

Linux aarch64, CPython 3.12, trusted Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. The implementation commit is the immutable single-parent commit `dfe51c5606a47641daeab3321651fcb949817d5b`; later commits are audit-only descendants. No Production data, registry publication, Owner private key, root Broker, or independent reviewer signing key was used.
