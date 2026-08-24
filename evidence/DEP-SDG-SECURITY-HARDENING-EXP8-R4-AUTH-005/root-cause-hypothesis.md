# Root Cause Hypothesis

## Hypothesis

The category allowlist permitted `decision_package`, while the successful decision-reuse branch returned before calling the strict `build_action_required` validator.

## Supporting evidence

Fresh review reproduced the bypass only when a package was present; top-level foreign authority fields were already rejected correctly.

## Contradicting evidence

Receipt signature, exact ID/scope, assumption freshness, and top-level closed schema all remained valid.

## Falsification test

Forbid every `decision_package` on a successful existing-decision reuse request, then test both nested-foreign and valid-but-unneeded packages.

## Conclusion

Confirmed. Reuse and escalation packages are mutually exclusive request states.
