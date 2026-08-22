# Agentic SDD Governance

[English](README.md) | [繁體中文](README.zh-TW.md)

Agentic SDD Governance (SDG) is an authorization, evidence, and risk-governance layer for autonomous software engineering Agents. It does not write code for the Agent. It tells Codex, Hermes, and similar systems what is already authorized, when they must stop, what debugging evidence is required, and how a Merge can be proven safe.

> SDG is experimental. It is executable and testable, but fixture benchmarks do not prove that it is superior to another workflow. Pilot it with synthetic or staging data before adopting it for sensitive systems.

SDG v1.2 Hard Gates close three common trust gaps: unknown or dangerous actions cannot call themselves L1, L2/L3 approvals require signed exact-scope receipts, and a Pull Request never supplies the verifier that judges that same Pull Request. See [`docs/HARD_GATES_V1_2.md`](docs/HARD_GATES_V1_2.md).

## Understand it in 30 seconds

From a source checkout (the script uses the repository virtual environment when present, otherwise the current Python environment with SDG's dependencies):

```bash
./demo/run.sh
```

Or with an installed CLI:

```bash
sddgov pilot quick
```

The offline synthetic demo shows five boundaries:

```text
Routine L1 engineering                     -> CONTINUE
L1 request hiding destructive Production   -> BLOCKED
Synthetic credential in Evidence           -> REDACTED
Unreviewed binary Evidence                  -> BLOCKED
Agent installation + strict DEP             -> VERIFIED
```

The demo uses no network, credentials, real users, Production system, or privileged service.

## Runtime model

Agents do not read the entire governance repository. Routine work loads only:

```text
Policy Kernel
  + one selected Profile
  + the current Work Package
  + the relevant Playbook
```

Start at `core/POLICY_KERNEL.md`. For development or debugging, use `skill/agentic-sdd-governance/SKILL.md`.

Debugging and regression work follows:

```text
Red -> Evidence -> Fix -> Green -> Proof
```

Raw evidence remains local under `private/raw`. Only verified, locally redacted text or an explicitly reviewed derivative may enter `shareable/artifacts`.

## Where SDG fits

- Feature development, bug fixes, refactoring, and Pull Request review.
- Cross-machine Codex or Hermes workflows.
- Systems that require Root Cause, Fix Scope, Regression, Rollback, and provenance records.
- Teams that need to prevent repeated hosted CI runs from becoming a remote debugger.
- Multi-Agent engineering that must distinguish routine work from L2 product decisions and L3 operations.

SDG does not perform Billing changes, MFA, real payments, Production data deletion, credential rotation, or other Owner-controlled actions on its own.

## Install the CLI

### Fast trial path

After the RC is available on PyPI, create an isolated environment and install the exact pre-release:

```bash
python3 -m venv .venv-sddgov
.venv-sddgov/bin/python -m pip install --pre 'agentic-sdd-governance==0.2.0rc1'
.venv-sddgov/bin/sddgov --version
.venv-sddgov/bin/sddgov pilot quick
```

Use this path for synthetic evaluation and local trials. Do not silently float to a newer RC in governed repositories; pin the reviewed version.

### Controlled verified path

After the matching `v0.2.0rc1` GitHub Release has been published, a controlled offline installation on Linux x86_64 with CPython 3.12 can download the inventoried runtime bundle and registry checksum, then let the machine verify the archive and every file inside it. These commands fail before publication because there is no matching release asset to download:

```bash
set -eu
test "$(uname -s)" = "Linux"
test "$(uname -m)" = "x86_64"
mkdir -p sdg-release
gh release download v0.2.0rc1 \
  --repo zycaskevin/Agentic-SDD-Governance \
  --pattern '*-offline-linux-x86_64-py312.zip' \
  --pattern 'SHA256SUMS.txt' \
  --dir sdg-release

archive_count=$(find sdg-release -maxdepth 1 -type f -name '*-offline-linux-x86_64-py312.zip' | wc -l | tr -d ' ')
test "$archive_count" -eq 1
verified_archive=$(find sdg-release -maxdepth 1 -type f -name '*-offline-linux-x86_64-py312.zip' -print -quit)
(cd sdg-release && awk -v name="$(basename "$verified_archive")" 'NF == 2 && $2 == name { print }' SHA256SUMS.txt > offline.SHA256SUMS)
(cd sdg-release && test "$(wc -l < offline.SHA256SUMS | tr -d ' ')" -eq 1)
(cd sdg-release && sha256sum -c offline.SHA256SUMS)
python3.12 -c 'import sys; assert sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12)'
python3.12 -m zipfile -e "$verified_archive" sdg-release/extracted

bundle_count=$(find sdg-release/extracted -mindepth 1 -maxdepth 1 -type d -name '*-offline-linux-x86_64-py312' | wc -l | tr -d ' ')
test "$bundle_count" -eq 1
bundle_root=$(find sdg-release/extracted -mindepth 1 -maxdepth 1 -type d -name '*-offline-linux-x86_64-py312' -print -quit)
(cd "$bundle_root" && sha256sum -c SHA256SUMS.txt)
wheel_count=$(find "$bundle_root/distributions" -maxdepth 1 -type f -name '*-py3-none-any.whl' | wc -l | tr -d ' ')
test "$wheel_count" -eq 1
project_wheel=$(find "$bundle_root/distributions" -maxdepth 1 -type f -name '*-py3-none-any.whl' -print -quit)

python3.12 -m venv .venv-sddgov
.venv-sddgov/bin/python -m pip install \
  --no-index --find-links "$bundle_root/wheelhouse" --require-hashes \
  -r "$bundle_root/requirements-governance.lock"
.venv-sddgov/bin/python -m pip install --no-index --no-deps "$project_wheel"
.venv-sddgov/bin/sddgov --version
.venv-sddgov/bin/sddgov pilot quick
```

The RC1 offline dependency bundle is intentionally platform-specific. macOS and other supported POSIX targets without a matching bundle should use the exact PyPI RC in an isolated online environment. Native Windows may use that path only for documentation and synthetic evaluation: descriptor-bound Evidence mutation, release helpers, Merge/rollback verification, and the L3 Broker are supported on Linux and macOS; use WSL2 for a full governed workflow. Private Release downloads require an authenticated GitHub CLI. Never paste a token or checksum into chat for human validation.

### Contributor source path

```bash
git clone https://github.com/zycaskevin/Agentic-SDD-Governance.git
cd Agentic-SDD-Governance
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/sddgov validate .
./demo/run.sh
```

Python 3.10 or newer is required.

## Install into a Codex project

```bash
SDDGOV_BIN="$(pwd)/.venv-sddgov/bin/sddgov"  # use "$(pwd)/.venv/bin/sddgov" from a contributor checkout
"$SDDGOV_BIN" setup-agent /absolute/path/to/project \
  --agent codex \
  --profile team-standard
"$SDDGOV_BIN" doctor /absolute/path/to/project
"$SDDGOV_BIN" status /absolute/path/to/project
```

Open a fresh Codex task after setup so it rediscovers the repository `AGENTS.md` and `.agents/skills/` path.

Suggested discovery check:

```text
Tell me which Governance Profile this repository uses and which minimum files
must be read before development. Do not change code yet.
```

A correct response discovers the Skill, reads the Policy Kernel and one Profile, locates the current Work Package, and avoids loading every governance document.

## Install into a Hermes project

```bash
SDDGOV_BIN="$(pwd)/.venv-sddgov/bin/sddgov"  # use "$(pwd)/.venv/bin/sddgov" from a contributor checkout
"$SDDGOV_BIN" setup-agent /absolute/path/to/project \
  --agent hermes \
  --profile team-standard
"$SDDGOV_BIN" doctor /absolute/path/to/project
```

Hermes file installation is supported, but host-specific discovery still requires a fresh runtime pilot. If the host does not discover the Repo Skill, use the root `AGENTS.md` as the workspace-instruction entry point. Do not copy the entire governance layer into `SOUL.md`.

## What setup manages

`setup-agent` manages only these paths and marked blocks:

```text
AGENTS.md                                      governance marked block only
.gitignore                                     raw-evidence marked block only
.agents/skills/agentic-sdd-governance/        discoverable Repo Skill
.agentic-sdd-governance/                       versioned governance resources
.sddgov/                                       repository governance state
```

Existing unrelated `AGENTS.md` and `.gitignore` content is preserved. If a managed file was modified, setup, upgrade, or uninstall fails closed until the difference is reviewed.

## Profiles

| Profile | Intended use | Main behavior |
|---|---|---|
| `solo-fast` | Individual and low-risk prototypes | Favors speed; credentials, Production, privacy, payment, and other sensitive boundaries still escalate. |
| `team-standard` | Normal team and multi-Agent development | Requires Issue/PR records, independent review, Local Green, and a full DEP for L1 regressions. |
| `regulated` | High-audit or high-risk environments | Adds provenance, second risk review, strict redaction, and complete L3 rollback proof. It is not a legal certification. |

## L0-L3 authority levels

| Level | Examples | Agent behavior |
|---|---|---|
| L0 | Documentation, a bounded non-regression fix, an explicit local task | Complete autonomously and provide targeted proof. |
| L1 | Regression, cross-module change, authentication, reliability, data flow | Gather evidence first, create a full DEP, and complete the approved scope autonomously. |
| L2 | Product behavior, quota, pricing, privacy, or public API change | Research and safe prototypes may continue, but one bounded Owner decision is required before changing the contract. |
| L3 | Production, payment, formal data deletion, credentials, MFA | Prepare dry run, exact operation, rollback, and proof; the concrete operation requires explicit signed authorization. |

Evidence can increase confidence. It never lowers the authority level.

### Owners decide; machines build the receipt

An L2 gate does not turn the Owner into a code reviewer. `sddgov decision show-product-approval` validates and displays one bounded A/B card; it cannot sign. The separately installed `sddgov-owner` client asks for one choice on an Owner-controlled terminal, computes the assumptions, nonce, and receipt, delegates to a confirmation-constrained external Ed25519 signer, and verifies the result. The Owner never edits JSON, compares hashes, pastes a signature, or exposes a private key. Independent Review, tests, Evidence, and Merge verification remain Agent/machine work. See the [Owner Key Ceremony](docs/OWNER_KEY_CEREMONY.md).

## Evidence quick start

```bash
sddgov evidence init --issue ISSUE-128 --risk L1 --sdd FAMILY-03
sddgov evidence collect evidence/DEP-... --collector terminal --input failing-test.log
sddgov evidence redact evidence/DEP-...
sddgov evidence transition evidence/DEP-... evidence
```

Complete the hypothesis, fix scope, regression, verification, and rollback documents while advancing one phase at a time. Before attachment:

```bash
sddgov evidence verify evidence/DEP-... --strict
sddgov evidence attach evidence/DEP-... --target pr
```

`attach` creates a local Markdown block. It does not post externally. Raw evidence remains under `private/raw` and is never attachable.

## CI Cost Guard

Before Push:

```bash
sddgov ci verify .
sddgov ci local-gate .
```

The guard enforces read-only default permissions, stale-run cancellation, Draft PR runner avoidance, bounded timeouts, and the repository hosted-run budget. A failed revision must be reproduced locally and fixed before another hosted run; CI is not a remote debugging loop.

See [`docs/CI_COST_GUARD.md`](docs/CI_COST_GUARD.md).

## Autonomy and artifact integrity

Machine-verifiable questions remain machine work. SHA-256 values are generated and checked by commands, never by asking a person to compare strings:

```bash
sddgov artifact lock dist/package.whl \
  --release release-X \
  --output release.lock
sddgov artifact verify dist/package.whl --lock release.lock
```

Before Merge, the exact trusted Base supplies the verifier. Candidate code is data, not authority:

```bash
sddgov merge verify . --base-ref <exact-base-sha>
```

## Upgrade and uninstall

Upgrade the CLI first, then inspect the target installation:

```bash
sddgov doctor /absolute/path/to/project
sddgov setup-agent /absolute/path/to/project \
  --agent codex \
  --profile team-standard \
  --force
sddgov doctor /absolute/path/to/project
```

`--force` replaces only manifest-owned files and marked blocks. It is not permission to overwrite unrelated project instructions.

Remove managed integration files with:

```bash
sddgov uninstall-agent /absolute/path/to/project
```

Uninstall retains `.sddgov` and Evidence so claims, events, decisions, external-action records, and proof are not silently destroyed.

## Documentation

- [`docs/USER_GUIDE.zh-TW.md`](docs/USER_GUIDE.zh-TW.md): complete Traditional Chinese installation and operations guide.
- [`docs/AGENT_INSTALLATION.md`](docs/AGENT_INSTALLATION.md): setup, upgrade, Doctor, and removal behavior.
- [`docs/EVIDENCE_DRIVEN_SDD.md`](docs/EVIDENCE_DRIVEN_SDD.md): Evidence-driven development model.
- [`docs/AUTONOMOUS_DEVELOPMENT_V1_2.md`](docs/AUTONOMOUS_DEVELOPMENT_V1_2.md): autonomy and escalation contract.
- [`docs/HARD_GATES_V1_2.md`](docs/HARD_GATES_V1_2.md): signed approval, trusted Base, Broker, Merge, and rollback gates.
- [`docs/OWNER_KEY_CEREMONY.md`](docs/OWNER_KEY_CEREMONY.md): per-domain Owner keys, rotation, revocation, and loss recovery.
- [`docs/L3_BROKER_OPERATIONS.md`](docs/L3_BROKER_OPERATIONS.md): Linux, WSL2, and macOS Broker service and readiness runbook.
- [`docs/ROLLBACK_OPERATIONS.md`](docs/ROLLBACK_OPERATIONS.md): single-commit proof, squash mapping, and audited break-glass recovery.
- [`docs/CI_COST_GUARD.md`](docs/CI_COST_GUARD.md): local/hosted CI budget contract.
- [`docs/ROADMAP.md`](docs/ROADMAP.md): measured evolution plan.

## Repository map

- `core/`: small mandatory Policy Kernel.
- `profiles/`: project-specific governance weight.
- `skill/`: thin Skill trigger and one-level on-demand references.
- `schemas/`: DEP, decision, approval, and collector contracts.
- `collectors/`: stack-specific evidence playbooks.
- `redaction/`: local sharing boundary.
- `src/sddgov/`: executable CLI.
- `demo/`: offline first-run demonstration.
- `services/`: reviewed systemd and launchd Broker service templates.
- `benchmarks/`: paired evaluation tasks and performance harnesses.
- `scripts/benchmark_monorepo_rollback.py`: exact-tree latency benchmark before any monorepo optimization.
- `templates/` and `.github/`: engineering and release records.

## Release and trust status

- `v0.2.0-experimental.8` is the latest completed experimental release.
- `0.2.0rc1` is the prepared PyPI pre-release target; publication remains an explicit external release action.
- Public release requires final exact-Head review, protected-file review proof, Local Green, package/fresh-wheel checks, provenance or attestations, and independently downloaded artifact verification.
- Owner private keys, Production credentials, and L3 Broker state must remain outside the repository and Agent workspace.

## Known limitations

- SDG is not a legal, medical, payment, or security certification.
- `doctor` proves installation integrity, not Agent behavior; run a fresh-session pilot.
- Redaction limits each source to 10 MiB, each decoded logical line to 1,048,576 characters, and retains 64 KiB of cross-chunk context so split credentials are still detected. Unsupported binary files fail closed pending explicit review. These controls reduce accidental disclosure but do not certify legal anonymization.
- Fixture benchmark results validate the harness, not superiority over another system.
- Host-specific Hermes behavior, root Broker provisioning, and sensitive-data adoption require environment-specific pilots.
- Security-sensitive descriptor-relative filesystem workflows support Linux and macOS; native Windows is limited to documentation and synthetic evaluation, with WSL2 required for a full governed workflow.

Before changing a private repository to public, follow [`docs/PUBLIC_RELEASE_CHECKLIST.zh-TW.md`](docs/PUBLIC_RELEASE_CHECKLIST.zh-TW.md). Security reports and contributions are covered by [`SECURITY.md`](SECURITY.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
