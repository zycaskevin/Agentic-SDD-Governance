# Regression Evidence

## Regression test added or strengthened

The existing Merge Gate positive/negative rollback suite enforces implementation-only refs, no later non-Evidence descendants, conflict-free inversion, and exact Base tree equality. This candidate adds a disposable exact-history drill proving those assertions for `2d8497e...`.

## Related tests executed

Actual revert of `2d8497efe36f394637f8a224c70a32167f69bbd5` succeeded; the non-Evidence/non-audit diff against Base was empty; reconciled Base Doctor passed with 64 managed files; the reverted full test suite passed.

## Unaffected paths sampled

The candidate content remains the same tree already covered by 221 tests, validate, CI Guard, Doctor, all portable Proof DEPs, fresh Codex/Hermes installs, and the offline synthetic pilot.
