# Reproduction

## Expected

Every reviewed release byte must come from the same validated open file description; transient Broker listener errors must not terminate the daemon; CI exceptions, evidence closure, redaction, runtime validation, rollback benchmarking, documentation, and Proof inventory checks must fail closed at their exact boundaries.

## Actual

PR #29 review identified 11 actionable findings and 14 nitpicks. The focused Red suite ran 157 tests and produced 10 failures plus 5 errors. Failures covered Evidence input read ordering, blank and duplicate workflow exemptions, Broker service hardening and runbook wording, Red evidence command ordering, missing broker/pilot source validation, benchmark decision state, transient `accept()` survival, release descriptor API, and bounded GitHub API retries.

## Deterministic steps

1. Check out reviewed Head `1849aa933c82e90b3e6eb194eaf6fde05e21e2dc` from PR #29.
2. Add the regression assertions represented by `terminal--r8-red-tests.txt` without changing implementation.
3. Run the focused unittest command shown in that artifact.
4. Observe 157 tests with 10 failures and 5 errors; verify each error maps to an exact review finding rather than an unrelated environment failure.

## Environment and preconditions

Linux aarch64, Python 3.12, trusted Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. Review identity is bound in `git--r8-review-bindings.txt`. No Production data, private key, root service, TestPyPI/PyPI credential, or public release was used.
