# Work Package: SDG Autonomous Development v1.2

## References

- Issue: #3
- Change proposal: `docs/AUTONOMOUS_DEVELOPMENT_V1_2.md`
- Risk: L1 governance implementation; Production, Secret, permission, destructive-data, and public-release actions remain outside this Work Package.

## Objective Contract

- Outcome: After an approved SDD Baseline and a start instruction, the Agent Team continues routine engineering without treating machine-verifiable state as a human approval prompt.
- Success metric: Every required autonomy Acceptance Test passes and SHA-256 remains machine-generated, machine-verified, and invisible during normal operation.
- Guardrails: Do not weaken L2/L3 authority, local-evidence redaction, rollback, Production, Secret, permission, or destructive-data protections.
- Keep condition: Exact-scope Decision Memory, one-use L3 approval, and all Production guardrails remain fail-closed.
- Rollback condition: Revert the autonomy runtime, policy, schemas, adapters, and related documentation as one coherent module.

## Scope

- In scope: Policy Kernel, machine-readable policy, escalation classifier, Decision Memory, Checkpoint contract, strict Decision Package, artifact lock/verify, Production deployment evaluator, Skill/adapters, tests, Changelog, and Roadmap.
- Non-scope: A real Production deployment, credential use, repository visibility, hosted Actions spending, destructive operations, or an unapproved product change.
- Dependencies: Existing Policy Kernel, Profiles, installer resources, CLI, and Evidence-Driven SDD module.
- Evidence requirement: keyword/layer audit, repository validation, full unit tests, Local Green Gate, packaging verification, and independent review.
- Verification plan: Prove L0/L1 autonomy, exact-scope L2 reuse, fresh one-use L3 approval, non-pausing Checkpoints, artifact mismatch containment, and guarded L1 deployment.

## Audit conclusion

No canonical pre-v1.2 Policy, CLI, Workflow, Guard, Prompt, Git history, or open PR explicitly required the owner to paste a SHA-256. Existing digest implementations were machine-generated. The failure was an Agent behavior made possible by missing executable escalation, Decision Memory, Checkpoint, artifact-integrity, and deployment contracts.
