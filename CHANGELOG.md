# Changelog

## 0.2.0-experimental — 2026-08-08

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

- Reduced routine Agent context to Policy Kernel + Profile + Work Package + relevant Playbook.
- Moved detailed evidence material out of the README and Skill entrypoint.

### Security

- Raw evidence is local-only and cannot be attached by the CLI.
- Binary artifacts fail closed pending manual review.
- Evidence does not expand L0–L3 authority.

### Evidence

- Release verification commands and results are recorded in `RELEASE_NOTES.md` after packaging.
