# Changelog

## 0.2.0-experimental.6 — Unreleased

### Added

- Added fail-closed canonical action and sensitive-effect classification so dangerous work cannot be downgraded by a caller-supplied L0/L1 label.
- Added trusted Ed25519 L3 approval receipt import, exact operation binding, nonce replay protection, expiry validation, and atomic single-use consumption on `CONTINUE`.
- Added executable `sddgov merge verify` enforcement for exact change digest, Local Green, strict DEP, Redaction, Rollback, raw-evidence exclusion, and protected-file independent Review.
- Added schemas, templates, documentation, and adversarial tests for all three Hard Gates.
- Added review-bound Merge metadata digests, trusted-base policy/key resolution, structured Rollback validation, and full commit-history raw Evidence scanning.

### Security

- Removed the string-only `decision authorize-operation` and separate `consume-operation` trust paths.
- Made unknown categories, dangerous downgrades, malformed receipts, untrusted signers, tampering, replay, stale approval, dirty worktrees, and missing Merge receipts fail closed without creating routine human approval prompts.
- Prevented candidate branches from authorizing themselves by modifying protected-path policy or reviewer keys, and rejected duplicate trust-store identities before key selection.
- Removed the candidate worktree approver store from L3 authority, required a trusted Base or out-of-band public-key source, and bound Merge reviews to an immutable base SHA.
- Bound DEP and Rollback content plus the exact reviewed Head into Merge authorization, rejected non-audit post-review commits and protected-path rename bypasses, and made malformed stored expiry timestamps fail closed.

### Changed

- GitHub Governance now checks out the exact PR head without persisted credentials, fetches full history, and executes the Merge verifier for non-Draft pull requests and `main` pushes.
- Moved signed provenance receipts and protected Merge enforcement forward from the v0.3 Roadmap.

## 0.2.0-experimental.5 — 2026-08-13

### Added

- Added SDG Autonomous Development v1.2 with executable escalation classification, Decision Memory, informational Checkpoints, and strict `ACTION REQUIRED` packages.
- Added machine-only artifact `lock` and `verify` commands; SHA-256 remains in provenance but is never a human approval token.
- Added bounded Production deployment evaluation with exact recorded Baseline scope and eight mandatory machine guardrails.
- Added acceptance tests for autonomous L0/L1 work, non-pausing Checkpoints, decision reuse, one-use L3 approval, artifact mismatch containment, and unrelated Work Package continuation.

### Security

- Prevented `machine_verifiable` claims and caller-supplied booleans from bypassing L3 or Production authority.
- Bound L2 Decision reuse and L1 routine Production deployment to exact recorded scopes and unchanged assumptions.
- Serialized Decision Store mutations so concurrent Agents cannot consume one L3 approval twice or overwrite each other's decisions.
- Rejected platform-normalized and symlink-redirected Evidence destinations and strengthened quoted secret-field redaction.
- Made browser evidence sharing deny-by-default for sensitive URL, identity, provider, runtime, connector, OAuth, bot/admin, and Supabase service-role data.
- Rejected C0/DEL control characters in raw and shareable evidence paths and activated RFC 3339 `date-time` validation through JSON Schema `FormatChecker`.
- Bound L2/L3 attachments to approved package state, Decision Package or explicit operation approval, authorized destination, and minimum disclosure.

### Changed

- Made Flutter, terminal, Supabase, and Docker collection examples bounded, private-path explicit, and failure-preserving.
- Clarified that every regression fix is L1/full-DEP, while ordinary approved bug fixes are not L2 merely because broken observed behavior changes.
- Narrowed uninstall retention claims to shareable evidence and recorded a repository-owner cleanup obligation for local raw evidence.
- Added explicit strict DEP verification commands, rejected root-cause status, and repository-relative CI Cost Guard setup.

## 0.2.0-experimental.4 — 2026-08-11 local integration candidate

### Security

- Restricted evidence paths to normalized `private/raw/` and `shareable/` descendants without traversal or backslash aliases.
- Added explicit password, patient-identifier, and customer-identifier redaction rules.

### Changed

- Preserved repository bootstrap instructions before layered Governance Root loading.
- Required non-blank Objective Contract list entries and safer collector reproduction context.
- Cancelled active pull-request CI when a PR is converted back to Draft.

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
