# Agentic SDD Governance

Experimental governance and evidence infrastructure for autonomous software engineering.

This repository answers four questions:

1. What has the Agent already been authorized to do?
2. When may it interrupt a human?
3. What evidence is required before a fix or Merge?
4. How do we measure whether the workflow works?

## Runtime model

Agents do **not** read the whole repository. Routine work loads:

```text
Policy Kernel + selected Profile + current Work Package + relevant Playbook
```

Start at `core/POLICY_KERNEL.md`. For development or debugging, use `skill/agentic-sdd-governance/SKILL.md`.

## Install into a project

After installing the CLI, add a discoverable Codex or Hermes integration without replacing existing project instructions:

```bash
sddgov setup-agent /path/to/project --agent codex --profile team-standard
sddgov doctor /path/to/project
```

The installer manages a marked block in `AGENTS.md`, a Repo Skill under `.agents/skills/`, and a versioned governance layer under `.agentic-sdd-governance/`. See `docs/AGENT_INSTALLATION.md` for upgrades, removal, and safety behavior.

## Evidence quick start

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .

evidence init --issue ISSUE-128 --risk L1 --sdd FAMILY-03
evidence collect evidence/DEP-... --collector terminal --input failing-test.log
evidence redact evidence/DEP-...
evidence transition evidence/DEP-... evidence
```

Complete the hypothesis, fix-scope, regression, verification, and rollback templates while advancing one phase at a time. Before attachment:

```bash
evidence verify evidence/DEP-... --strict
evidence attach evidence/DEP-... --target pr
```

`attach` produces a local Markdown block; it does not post externally. Raw evidence remains under `private/raw` and is never attachable.

## Profiles

- `solo-fast`: low-risk speed with safety escalation for sensitive areas.
- `team-standard`: Issue/PR, independent review, and full DEP for L1 debugging.
- `regulated`: provenance, second risk review, local redaction, and strict L3 proof.

## Repository map

- `core/`: small mandatory Policy Kernel.
- `profiles/`: project-specific governance weight.
- `skill/`: thin trigger and one-level on-demand references.
- `schemas/`: DEP and collector contracts.
- `collectors/`: stack-specific evidence playbooks.
- `redaction/`: local sharing boundary.
- `src/sddgov/`: executable CLI.
- `benchmarks/`: paired evaluation tasks and scoring.
- `templates/` and `.github/`: engineering record fields.
- `src/sddgov/installer.py`: idempotent Agent setup, health checks, and guarded removal.

This is an experimental framework. Fixture benchmark results test the harness; they do not prove superiority over another workflow.

## License

Apache License 2.0. See `LICENSE`.
