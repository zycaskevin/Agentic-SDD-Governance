# Agent Installation

This module is loaded when installing, upgrading, checking, or removing Agentic SDD Governance in another repository. It is not routine Agent context.

## Setup

Install the Python package, then run one command from any directory:

```bash
sddgov setup-agent /path/to/project --agent codex --profile team-standard
```

Supported agents are `codex` and `hermes`. Supported Profiles are `solo-fast`, `team-standard`, and `regulated`.

Setup preserves existing project instructions and manages only:

```text
AGENTS.md                                      marked governance block only
.gitignore                                     raw-evidence block only
.agents/skills/agentic-sdd-governance/        discoverable Skill
.agentic-sdd-governance/                      versioned governance resources
.sddgov/                                      state initialized when absent
```

Codex officially scans `.agents/skills` from the current directory through the repository root. The installed layout follows that contract: <https://learn.chatgpt.com/docs/build-skills>.

## Verify

```bash
sddgov doctor /path/to/project
sddgov status /path/to/project
```

`doctor` verifies the install manifest, SHA-256 hashes, the managed `AGENTS.md` and `.gitignore` blocks, the selected Profile, and the Skill discovery path. A clean result proves the files and routing contract are installed; it does not replace a fresh-Agent behavior pilot.

## Idempotence and upgrades

Running the same setup again is a no-op. A different Agent, Profile, CLI version, or modified managed file causes setup to stop. Review `doctor` output before explicitly allowing a managed replacement:

```bash
sddgov setup-agent /path/to/project --agent hermes --profile solo-fast --force
```

`--force` may replace only paths owned by the install manifest and marked governance blocks. It does not replace unrelated `AGENTS.md` or `.gitignore` content.

## Remove

```bash
sddgov uninstall-agent /path/to/project
```

Removal fails closed when a managed file or governance block was modified. After review, `--force` permits removal of those managed files. Uninstall retains `.sddgov` and `evidence` so claims, events, external-action records, raw evidence, and proof are not silently destroyed.

## Pilot acceptance

A real Agent pilot should confirm that the Agent:

1. Discovers `agentic-sdd-governance` in a fresh session.
2. Reads the Policy Kernel, one Profile, the current Work Package, and only the relevant Playbook.
3. Creates a DEP for an L1 failure and follows Red -> Evidence -> Fix -> Green -> Proof.
4. Redacts an injected fake secret before creating a shareable Evidence Block.
5. Stops before an unapproved L2 product decision or concrete L3 action.
6. For an assigned independent Review, refuses a dirty checkout, bootstraps its own Repo-external Reviewer identity, registers public trust directly, and signs the exact approved Merge gate without asking the owner for key material.

Hermes file-level installation is supported by the adapter and open Skill layout. Its host-specific discovery and invocation still require a Hermes runtime pilot.
