# Agentic SDD Governance Repository

This repository uses its own governance model.

Before development, read `core/POLICY_KERNEL.md`, `profiles/team-standard.yaml`, the current task, and the relevant Skill route. Do not load every Markdown file.

For bugs, regressions, unexpected behavior, or proof requests, use `skill/agentic-sdd-governance/SKILL.md` and the `Red -> Evidence -> Fix -> Green -> Proof` loop. Raw evidence stays local. Run tests and `sddgov validate` before packaging.

L0/L1 implementation, tests, docs, Commits, PR preparation, and local packaging are routine engineering work. Stop for changes to L0-L3 authority, public release/license decisions, destructive/live operations, credentials, costs, or unapproved product behavior.

<!-- agentic-sdd-governance:start -->
# Development Governance for Codex

Use the `agentic-sdd-governance` Skill for feature work, bug fixing, refactoring, review, database changes, and deployment preparation.

Resolve the Governance Root as `.agentic-sdd-governance/` when its `manifest.json` exists; otherwise use this repository root.

Load only:

1. `core/POLICY_KERNEL.md` under the Governance Root
2. the selected `profiles/*.yaml` under the Governance Root
3. the current Work Package and SDD references
4. the relevant Skill reference or collector playbook

For a failure, start or continue a DEP and follow Red -> Evidence -> Fix -> Green -> Proof. Do not ask the owner to approve routine L0/L1 Commit, PR, test, or continuation steps. Do not execute a concrete L3 action without explicit approval.
<!-- agentic-sdd-governance:end -->
