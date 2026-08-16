# Root Cause Hypothesis

## Hypothesis

Rollback parsing validates lexical shape but lacks trusted Base context and Git graph context. It also treats arbitrary colon-free text as ignorable prose.

## Supporting evidence

Fresh hostile tests reproduce `HEAD`, nonexistent ref, unrestricted v1, and standalone-text acceptance. CodeRabbit and a second independent Reviewer identified the same boundaries independently.

## Contradicting evidence

The verifier never executes rollback strings and exact Gate/Receipt binding still works. These controls reduce immediate execution risk but do not make an unusable or out-of-scope rollback plan valid.

## Falsification test

Pass Base SHA, reviewed Head, and rollback path into validation; require an exact bootstrap tuple for v1; extract a full SHA and prove `base < ref <= reviewed_head` in Git; reject every unknown non-comment line. The original RED tests must turn Green while canonical v2 remains valid.

## Conclusion

Confirmed. The missing context and permissive lexical rules are the direct causes.
