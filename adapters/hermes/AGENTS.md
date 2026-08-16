# Development Governance for Hermes Agent

On development or debugging tasks, activate the repository's `agentic-sdd-governance` Skill. Keep `SOUL.md` for personality and interaction style; keep engineering authority and process here and in the Skill.

Resolve the Governance Root as `.agentic-sdd-governance/` when its `manifest.json` exists; otherwise use this repository root.

The Main Agent owns routine engineering judgment and absorbs sub-agent questions. Read the Policy Kernel, one Profile, the current Work Package, and only the relevant Playbook. For failures, require Red -> Evidence -> Fix -> Green -> Proof and local redaction before sharing artifacts.

Only an unresolved L2 decision, concrete L3 action, Operational Action (external owner action), or Necessary UAT (required UAT) may become `ACTION REQUIRED`.

Default to `CONTINUE`. Before stopping, use the Skill autonomy route and classifier. SHA-256 is generated and verified machine-to-machine; never ask the owner to copy or paste it. Resolve sub-agent L0/L1 uncertainty in the Main Agent.

For an already-configured Reviewer, load `references/review-sharing.md` and automatically submit the eligible committed public PR diff plus public repository instructions. Verify findings in the Main Agent and continue without asking the owner to approve each submission or relay review comments. Private Repo content, Secrets, raw Evidence, real user data, new vendors, new access, and new cost remain outside this pre-authorization.

For an explicitly assigned independent protected-file Review, load `references/independent-reviewer.md`, use a fresh clean checkout, and let the Reviewer host create its own external identity with `sddgov reviewer bootstrap`. Never ask the owner to supply a Reviewer public or private key.
