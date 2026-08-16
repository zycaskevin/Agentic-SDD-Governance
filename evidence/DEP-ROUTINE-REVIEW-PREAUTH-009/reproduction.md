# Reproduction

## Expected

An Agent automatically sends the minimum committed public PR diff and public repository instructions to a Reviewer already configured for that public repository. The owner is not asked to approve each review submission or relay findings.

## Actual

At baseline `6a90ad84e8ed141241d3ca972b5ab91251429671`, the Policy Kernel, autonomy policy, Skill, and Codex/Hermes adapters contain no bounded review-sharing pre-authorization contract. An Agent can therefore treat ordinary review submission as a new external-data decision and interrupt the owner.

## Deterministic steps

1. In a clean disposable clone, run `git checkout --detach 6a90ad84e8ed141241d3ca972b5ab91251429671` and verify `git rev-parse HEAD` prints that exact SHA.
2. Inspect exactly `core/POLICY_KERNEL.md`, `policies/autonomy-policy.json`, `skill/agentic-sdd-governance/SKILL.md`, `adapters/codex/AGENTS.md`, and `adapters/hermes/AGENTS.md`.
3. Run `git grep -n 'AUTOMATIC_REVIEW_IS_PREAUTHORIZED' -- core/POLICY_KERNEL.md policies/autonomy-policy.json skill/agentic-sdd-governance/SKILL.md adapters/codex/AGENTS.md adapters/hermes/AGENTS.md` and require exit 1 with no output; any match fails the Red precondition.
4. Run `git grep -n 'references/review-sharing.md' -- core/POLICY_KERNEL.md policies/autonomy-policy.json skill/agentic-sdd-governance/SKILL.md adapters/codex/AGENTS.md adapters/hermes/AGENTS.md` and require exit 1 with no output; any match fails the Red precondition.
5. Compare the verified absence with the owner-confirmed expectation in Issue #13.

## Environment and preconditions

Public repository baseline, synthetic public text only, no Secrets, no raw user data, and no network use in the reproduction artifact.
