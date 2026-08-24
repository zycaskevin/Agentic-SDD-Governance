# Reproduction

## Expected

Machine-verifiable outcomes control process exit status; an owner sees at most one exact, correctly bound escalation; local state cannot impersonate owner authority; first-consumer and historical Evidence verification fail closed without becoming impossible to satisfy.

## Actual

The baseline returned exit 0 for blocked outcomes, did not fully bind Decision Packages, repeated Necessary UAT, lacked a signed external-action terminal transition, could not verify a first Governance PR, failed three portable Proof DEPs, and raised TypeError for malformed CI exemptions.

## Deterministic steps

1. Evaluate one routine, one unknown, and one L2 request through the CLI and record process exit status.
2. Repeat one identical Necessary UAT and inspect `.sddgov/external-actions.json`.
3. Change a pending local row to `completed` without an owner signature and reevaluate.
4. Run Merge verification against an ungoverned consumer Base.
5. Run portable strict verification for every tracked Proof DEP.
6. Verify a CI contract whose exemption list contains a non-string object.

## Environment and preconditions

Baseline `a5c27e306373829eee966222c3915f5a822b190c`; synthetic temporary repositories and state only; macOS arm64; Python 3.12; no network, credentials, Production data, or real user data in the reproduction.
