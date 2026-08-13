# Root Cause Hypothesis

## Hypothesis

The v1.2 Runtime correctly encoded intended outcomes but trusted caller classification and approval strings, while Merge requirements remained declarative.

## Supporting evidence

`evaluate_escalation` returned a blanket L0/L1 `CONTINUE` for any non-forced category; CLI minted L3 decisions from text flags; L3 evaluation only checked stored state without consuming it; the workflow ran tests and `validate` but never loaded `merge-policy.yaml`.

## Contradicting evidence

Existing routine L0/L1, strict Decision Package, Production guardrail, Decision Store lock, DEP, Redaction, and artifact-integrity tests were already effective and remained Green.

## Falsification test

Add adversarial tests for unknown/dangerous categories, forged/tampered/expired/replayed L3 receipts, concurrent L3 evaluation, missing protected-file review, and tracked raw Evidence.

## Conclusion

Confirmed. All four unsafe outcomes reproduced at merged main and became blocked after the bounded Hard Gate changes.
