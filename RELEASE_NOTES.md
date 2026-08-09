# v0.2.0-experimental.2 Release Notes

## Outcome

This release makes the Evidence-Driven SDD governance layer installable in another project. It adds guarded Codex/Hermes setup, official Codex Repo Skill discovery layout, health checks, managed upgrades, and recoverable removal while retaining the progressively disclosed DEP and evidence workflow.

The delivery history now includes the canonical GitHub `main` baseline at commit `402517808d22c3daa44811301e96c7964db3dc5a` and preserves its Apache License 2.0 file.

## Verification performed

- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 23 tests passed.
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
