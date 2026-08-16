# Root Cause Hypothesis

## Hypothesis

The functional repair was split across two implementation commits separated by Evidence. DEP-012 correctly rolled back its own increment but was incorrectly selected as proof for the complete PR-to-Base rollback contract.

## Supporting evidence

The independent Security reviewer measured 34 remaining non-Evidence paths after the old rollback. A disposable actual revert independently reproduced the incomplete Base restoration.

## Contradicting evidence

Each individual commit was internally reversible and all functional tests were Green; the defect was the full-candidate rollback boundary, not the implementation behavior.

## Falsification test

Create a boundary commit whose non-Evidence/non-audit tree equals Base, reapply the complete implementation in one atomic commit, then perform an actual revert and exact tree comparison at the candidate Head.

## Conclusion

Confirmed. The retained-history boundary/reapply sequence creates one auditable implementation unit without force-push or history rewriting.
