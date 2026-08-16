# Root Cause Hypothesis

## Hypothesis

The request-envelope validator was scoped to L0/L1, so the L2 decision-reuse path reached `_find_decision` and `_l2_approval_matches` before rejecting foreign authority fields.

## Supporting evidence

The independent reviewer reproduced `CONTINUE existing_decision_reused_without_duplicate_question` with a valid L2 receipt plus a structured L3 field. Code inspection confirmed the closed-envelope call was conditional on `risk in {L0, L1}`.

## Contradicting evidence

The signed L2 receipt itself remained valid and exact; the defect was in the outer request schema, not receipt signature verification or assumption freshness.

## Falsification test

Apply one closed per-category schema before every authorization branch, then repeat the exact reuse request with each foreign field independently.

## Conclusion

Confirmed. Category schema validation must be risk-independent and precede all decision and approval reuse.
