# Regression Evidence

## Regression test added or strengthened

`test_rollback_ref_must_apply_cleanly_at_the_reviewed_head` creates a later overlapping edit and requires Merge verification to reject the otherwise valid rollback ref.

## Related tests executed

Targeted Merge Gate tests, complete test suite, validate, CI semantic verification, seven predecessor DEP checks, package/fresh-install doctor, and offline synthetic pilot.

## Unaffected paths sampled

Full-SHA syntax, candidate ancestry, exact v1 bootstrap scope, standalone/duplicate/wrapper rejection, trusted review binding, and audit-only descendant handling.
