# v0.2.0-experimental.3 Release Notes

## Outcome

This release adds CI Cost Guard to the installable Evidence-Driven SDD governance layer. A repository declares its shell-free local Green Gate and bounded GitHub-hosted budget in `.sddgov/ci-cost-guard.json`; the CLI then verifies workflow controls or runs the complete local gate before a Push.

The progressively disclosed Skill now routes CI changes, failures, reruns, and cost questions to a short dedicated module. Existing Policy Kernel, Evidence, installer, and Codex/Hermes discovery behavior remain intact.

The delivery history now includes the canonical GitHub `main` baseline at commit `402517808d22c3daa44811301e96c7964db3dc5a` and preserves its Apache License 2.0 file.

## Verification performed

- `PYTHONPATH=src python3 -m sddgov.cli ci local-gate .`: 27 tests and repository validation passed.
- Static CI guard verification against Agentic SDD Governance, MyHermes, Vault-Agent-Memory, and Piku: passed.
- `PYTHONPATH=src python3 -m sddgov.cli validate .`: passed.
- Skill Creator `quick_validate.py`: passed.
- `python -m compileall -q src tests`: passed.
- PEP 517 sdist and wheel build with no runtime dependency downloads: passed.
- Clean wheel installation into an isolated Python 3.14 environment: passed.
- Installed CLI smoke: Codex/Hermes setup, doctor, project status, tamper detection, guarded uninstall, and DEP retention: passed.
- Codex `debug prompt-input` discovered the installed Repo Skill at `.agents/skills/agentic-sdd-governance/SKILL.md` while keeping the full Policy Kernel out of initial context: passed.
- Leak scan of the shareable smoke artifact for the injected bearer token and email: no match.

## Important limits

- The Local Redaction Gateway is a conservative MVP, not a legal anonymization certification.
- Screenshots, trace ZIPs, videos, archives, and other binary evidence fail closed until a manually reviewed derivative exists.
- Included benchmark scores are synthetic fixture checks; no superiority claim is allowed.
- Codex prompt-input Skill discovery and Hermes file-level installation are verified; a fresh-Agent behavior pilot and Hermes runtime pilot remain roadmap gates.
- The historical v0.1 attachment could not be retrieved byte-for-byte, and the current GitHub baseline contains only `LICENSE`. See `docs/BASELINE_PROVENANCE.md`.
- Remote Push, public release, and external claims remain owner actions. This package preserves the repository's existing Apache-2.0 license selection.
- Billing budgets, self-hosted runners, workflow dispatches, and Production workflows are not changed by CI Cost Guard.
