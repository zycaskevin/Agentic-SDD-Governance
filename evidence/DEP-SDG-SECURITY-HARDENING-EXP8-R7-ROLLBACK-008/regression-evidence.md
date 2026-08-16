# Regression Evidence

## Regression test added or strengthened

`test_rollback_ref_must_apply_cleanly_at_the_reviewed_head` creates a later overlapping edit and requires Merge verification to reject the otherwise valid rollback ref. Additional tests reject Evidence inside the selected commit, non-Evidence descendants, built-in `merge=union` partial rollback, and repository-configured external merge-driver execution.

## Related tests executed

Targeted Merge Gate tests, complete `198 passed + 144 subtests`, validate, CI semantic verification, eight DEP checks, package/fresh-install doctor, and offline synthetic pilot.

## Unaffected paths sampled

Full-SHA syntax, candidate ancestry, exact v1 bootstrap scope, standalone/duplicate/wrapper rejection, trusted review binding, and audit-only descendant handling.
