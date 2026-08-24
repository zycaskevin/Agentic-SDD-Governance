# Root Cause Hypothesis

## Hypothesis

Five adjacent contracts relied on permissive shortcuts: a caller boolean stood in for UAT evidence; argparse and process exceptions retained their default exit 2; durable row validation happened after lookup/mutation; first-consumer markers covered only one supported policy location; and resource lookup used the newer multi-child Traversable API despite a Python 3.10 package floor.

## Supporting evidence

Independent Autonomy and Security reviewers reproduced each failure from a fresh exact Head. The new focused regression suite failed in every expected pre-fix location.

## Contradicting evidence

Routine L0/L1 autonomy, subjective durable UAT, signed terminal action reuse, normal governed Bases, Python 3.11+, Evidence integrity, and rollback remained Green. They are regression boundaries, not evidence against the five gaps.

## Falsification test

Require the focused hostile tests to become Green while the full suite still proves zero new owner prompts for Issue, Commit, PR, Review, CI, Merge, retry, and checksum paths.

## Conclusion

Confirmed. The defects were machine-contract and trust-boundary gaps; none required a new human approval mechanism.
