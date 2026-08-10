# Changelog

## 0.2.0-experimental.3 — 2026-08-10

### Added

- CI Cost Guard policy, JSON Schema/template, Work Package, and progressive-disclosure Skill route.
- `sddgov ci verify` for fail-closed contract and GitHub workflow control checks.
- `sddgov ci local-gate` for shell-free, repository-configured local Green checks.

### Changed

- The governance workflow now cancels stale runs, avoids Draft PR runners, uses read-only permissions, and bounds job runtime.
- All Profiles now define hosted-run, rerun, and Full Matrix defaults without weakening acceptance criteria.

## 0.2.0-experimental.2 — 2026-08-09

### Added

- `sddgov setup-agent` for Codex or Hermes with selectable governance Profile.
- `sddgov doctor` for manifest, managed-file, Skill-path, `AGENTS.md`, and state verification.
- `sddgov uninstall-agent` with safe retention of `.sddgov` and Evidence.
- Wheel-packaged governance resources so setup works outside the source checkout.

### Changed

- Codex Skills are installed at the official Repo discovery path, `.agents/skills/agentic-sdd-governance/`.
- The Skill resolves `.agentic-sdd-governance/` as its installed Governance Root while retaining canonical-repository compatibility.

### Security

- Setup records SHA-256 hashes for every managed file and refuses ambiguous upgrades without `--force`.
- Setup adds a managed `.gitignore` rule so default `evidence/**/private/raw/` artifacts remain local.
- Doctor reports tampering; uninstall fails closed on modified managed files unless explicitly forced.
- Existing project instructions, governance state, and evidence are not silently removed.

### Evidence

- Codex/Hermes setup, idempotence, Profile switching, tamper detection, and guarded uninstall are covered by automated tests.

## 0.2.0-experimental.1 — 2026-08-08

### Added

- Evidence-Driven SDD and the `Red -> Evidence -> Fix -> Green -> Proof` protocol.
- Debug Evidence Package v1 schema, templates, provenance manifest, and two-zone storage.
- Local Redaction Gateway with deterministic secret/identifier masking and binary fail-closed behavior.
- Evidence CLI: `init`, `collect`, `redact`, `transition`, `verify`, and `attach`.
- Evidence fields for Issue, Commit, PR, and Changelog records.
- Collector interface and stack-specific playbooks.
- L0–L3 evidence/debugging matrix in all three governance Profiles.
- Thin Codex/Hermes Skill and adapters that load evidence modules only for development/debugging tasks.
- Paired benchmark harness for screenshot-only guessing versus Evidence-Driven Debugging.

### Changed

- Preserved the canonical GitHub Initial commit and Apache-2.0 `LICENSE` in the delivery history.
- Reduced routine Agent context to Policy Kernel + Profile + Work Package + relevant Playbook.
- Moved detailed evidence material out of the README and Skill entrypoint.

### Security

- Raw evidence is local-only and cannot be attached by the CLI.
- Binary artifacts fail closed pending manual review.
- Evidence does not expand L0–L3 authority.

### Evidence

- Release verification commands and results are recorded in `RELEASE_NOTES.md` after packaging.
