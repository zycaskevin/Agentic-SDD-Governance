# Reproduction

## Expected

Changing an Agent-loaded governance copy must be classified as a protected-file change by the trusted Base policy.

## Actual

`_is_protected` returned false for `AGENTS.md`, `.agents/skills/agentic-sdd-governance/SKILL.md`, and `.agentic-sdd-governance/core/POLICY_KERNEL.md`.

## Deterministic steps

1. Load the protected patterns from candidate `d03213a` trusted Base policy.
2. Evaluate the root bootstrap file and both installed governance-copy paths.
3. Observe that none requires a protected-file review receipt.

## Environment and preconditions

Fresh PR #12 checkout; no Production data, credentials, or live operations.
