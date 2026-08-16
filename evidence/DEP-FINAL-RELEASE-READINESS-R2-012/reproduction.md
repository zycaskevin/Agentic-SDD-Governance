# Reproduction

## Expected

Malformed or mismatched machine input returns structured `BLOCKED` with exit 1. Generic uncertainty never directly asks the owner. Both completed and cancelled terminal state requires a valid exact owner signature on every reuse. The candidate Repository passes Doctor with current installed governance.

## Actual

The final independent reviews reproduced four gaps: Decision Package failures could escape to the global exit-2 handler; uncertainty could produce `ACTION_REQUIRED`; cancelled state skipped signature revalidation; and the installed manifest omitted the new resolution Schema/template while loading older policy and workflow copies.

## Deterministic steps

1. Evaluate outer/inner product risk mismatch and malformed L3 package cases through the CLI.
2. Evaluate L2/L3 uncertainty with a caller-supplied package.
3. Reuse unsigned and signature-tampered cancelled external-action state.
4. Run `sddgov doctor .` against the candidate Repository.

## Environment and preconditions

Exact reviewed parent `ac0a1add18e4930ee07298431dda72ccc93011c4`; synthetic request and signed-receipt fixtures only; Repo-external Python environment; no credentials, Production state, or user data.
