# Agentic SDD Governance Repository

This repository uses its own governance model.

Before development, read `core/POLICY_KERNEL.md`, `profiles/team-standard.yaml`, the current task, and the relevant Skill route. Do not load every Markdown file.

For bugs, regressions, unexpected behavior, or proof requests, use `skill/agentic-sdd-governance/SKILL.md` and the `Red -> Evidence -> Fix -> Green -> Proof` loop. Raw evidence stays local. Run tests and `sddgov validate` before packaging.

L0/L1 implementation, tests, docs, Commits, PR preparation, and local packaging are routine engineering work. Stop for changes to L0-L3 authority, public release/license decisions, destructive/live operations, credentials, costs, or unapproved product behavior.

<!-- agentic-sdd-governance:start -->
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

For an already-configured Reviewer, load `references/review-sharing.md` and automatically submit the eligible committed public PR diff plus public repository instructions. Verify findings locally and continue without asking the owner to approve each submission or relay review comments. Private Repo content, Secrets, raw Evidence, real user data, new vendors, new access, and new cost remain outside this pre-authorization.

For an explicitly assigned independent protected-file Review, load `references/independent-reviewer.md`, use a fresh clean checkout, and create the Reviewer identity outside the Repo with `sddgov reviewer bootstrap`. Never ask the owner to provide a Reviewer key.
<!-- agentic-sdd-governance:end -->
