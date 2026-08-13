# Development Governance for Codex

Use the `agentic-sdd-governance` Skill for feature work, bug fixing, refactoring, review, database changes, and deployment preparation.

Resolve the Governance Root as `.agentic-sdd-governance/` when its `manifest.json` exists; otherwise use this repository root.

After completing the repository's required bootstrap reads, load only the following additional Governance Root sources:

1. `core/POLICY_KERNEL.md` under the Governance Root
2. the selected `profiles/*.yaml` under the Governance Root
3. the current Work Package and SDD references
4. the relevant Skill reference or collector playbook

For a failure, start or continue a DEP and follow Red -> Evidence -> Fix -> Green -> Proof. Do not ask the owner to approve routine L0/L1 Commit, PR, test, or continuation steps. Do not execute a concrete L3 action without explicit approval.

Default to `CONTINUE`. Before stopping, use the Skill autonomy route and classifier. Do not use a human as a checksum validator, CI runner, Git operator, retry button, or approval gate for reversible L0/L1 work. Sub-agent uncertainty routes to the Main Agent, not directly to the owner.
