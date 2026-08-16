# Reproduction

## Expected

An Agent automatically sends the minimum committed public PR diff and public repository instructions to a Reviewer already configured for that public repository. The owner is not asked to approve each review submission or relay findings.

## Actual

At baseline `6a90ad84e8ed141241d3ca972b5ab91251429671`, the Policy Kernel, autonomy policy, Skill, and Codex/Hermes adapters contain no bounded review-sharing pre-authorization contract. An Agent can therefore treat ordinary review submission as a new external-data decision and interrupt the owner.

## Deterministic steps

1. Read the baseline versions of `core/POLICY_KERNEL.md`, `policies/autonomy-policy.json`, `skill/agentic-sdd-governance/SKILL.md`, `adapters/codex/AGENTS.md`, and `adapters/hermes/AGENTS.md`.
2. Search for `AUTOMATIC_REVIEW_IS_PREAUTHORIZED` and `references/review-sharing.md`.
3. Observe zero matching policy/route contracts.
4. Compare that absence with the owner-confirmed expectation in Issue #13.

## Environment and preconditions

Public repository baseline, synthetic public text only, no Secrets, no raw user data, and no network use in the reproduction artifact.
