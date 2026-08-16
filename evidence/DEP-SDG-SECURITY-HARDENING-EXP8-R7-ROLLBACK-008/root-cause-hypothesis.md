# Root Cause Hypothesis

## Hypothesis

Rollback verification proves syntax, object identity, and ancestry but not whether the inverse patch can be applied to the reviewed Head. The declared implementation commit also touched Evidence that later commits modified.

## Supporting evidence

The independent reviewer reproduced four conflicts for the selected commit. All five unique historical rollback refs also failed a disposable no-commit drill.

## Contradicting evidence

The ref is a valid full SHA, exists, and is in the exact Base-to-Head range; those checks correctly pass and therefore do not explain the failure.

## Falsification test

Create an implementation-only commit whose paths are never modified by later Evidence/Gate/Receipt commits, bind it afterward, and require a tree-level reverse-merge simulation at verification time.

## Conclusion

Confirmed. Commit-boundary overlap plus the missing applicability check allowed a non-operational rollback plan to look valid.
