# Changelog

## 0.2.0-experimental.7 — 2026-08-15 security hardening candidate

### Security

- Separated the authoritative PR verifier from candidate code: the Base-controlled `pull_request_target` workflow installs the exact Base verifier, treats the candidate checkout only as data, and never executes candidate-defined Local Green commands.
- Made strict DEP verification reopen and recalculate every available artifact's normalized path, regular-file type, link count, size, and SHA-256; missing, altered, extra, escaped, symlinked, hardlinked, and duplicate artifacts now fail closed.
- Required every raw artifact to appear exactly once in deterministic `files` or fail-closed `blocked`; unknown/binary suffixes and every HAR are blocked from the generic text redactor.
- Prevented collector label overwrite, DEP ID path escape, redaction input/output symlink traversal, pre-rejection external directory creation, and pathname-reopen TOCTOU.
- Replaced caller-authored L2 authority with Owner Ed25519 receipts loaded from a separate-identity trust root and bound to assumption artifact paths whose current bytes are recalculated on every reuse.
- Bound L3 receipts to repository, project, environment, scope, category, target, non-secret parameters, and sensitive effects; `CONTINUE` now requires a root-owned clone-external atomic nonce broker.
- Made Base Reviewer revocation authoritative so a stale external bootstrap variable cannot reactivate a revoked key.
- Required the Base Reviewer store itself to match the exact bootstrap contract before any external key is accepted; missing or malformed Base state fails closed.
- Bound Evidence to Collector identity, immutable source suffix, and detected media type, and retained verified base/source/DEP/zone/output directory descriptors through DEP creation, collection, redaction, strict verification, attachment, and atomic control-document writes. Attachment generation now consumes the exact in-memory summary/manifest snapshot that strict verification checked; its write transaction checks control identity immediately before and after output, then removes a new default output or restores a prior custom output if a control swap is detected.
- Required L3 repository/project/environment to match a separate root-controlled Runtime Context, made outer/inner scope identical, rejected root Agent execution, and moved atomic nonce consumption to a root-provisioned Unix service on fixed macOS/Linux paths.
- Pinned privileged GitHub Actions to full commit SHAs and hash-locked every Python dependency used by the trusted verifier.

### Added

- Added L2 product-decision receipt Schema/template, an L3 Runtime Context Schema/template, a hashed Governance dependency lock, and expanded L3/Decision Record contracts.
- Added adversarial regression tests for Evidence tampering, path boundaries, authority downgrade, receipt tampering/replay, and exact L3 payload mismatch.
- Added an offline disposable synthetic Muse/Hermes pilot using synthetic relationship text and one generated image; binary sharing fails closed and the reviewed derivative completes full and portable DEP verification.

### Changed

- Added `sddgov evidence verify --portable` for Base-controlled PR verification where local raw bytes are intentionally absent; full local strict verification remains mandatory before attachment.
- Added `sddgov pilot synthetic-muse` for the bounded isolation pilot.
- Kept this version experimental: the synthetic pilot does not authorize Production, real Muse data, credentials, or L2/L3 operations.

## 0.2.0-experimental.6 — 2026-08-15

### Added

- Added fail-closed canonical action and sensitive-effect classification so dangerous work cannot be downgraded by a caller-supplied L0/L1 label.
- Added trusted Ed25519 L3 approval receipt import, exact operation binding, nonce replay protection, expiry validation, and atomic single-use consumption on `CONTINUE`.
- Added executable `sddgov merge verify` enforcement for exact change digest, Local Green, strict DEP, Redaction, Rollback, raw-evidence exclusion, and protected-file independent Review.
- Added schemas, templates, documentation, and adversarial tests for all three Hard Gates.
- Added review-bound Merge metadata digests, trusted-base policy/key resolution, structured Rollback validation, and full commit-history raw Evidence scanning.
- Added `sddgov reviewer bootstrap|export-trust|sign` so an independent Hermes/Codex host can provision owner-only Repo-external key material, register public trust, and sign the exact Merge gate without turning the product owner into a key courier.

### Security

- Removed the string-only `decision authorize-operation` and separate `consume-operation` trust paths.
- Made unknown categories, dangerous downgrades, malformed receipts, untrusted signers, tampering, replay, stale approval, dirty worktrees, and missing Merge receipts fail closed without creating routine human approval prompts.
- Prevented candidate branches from authorizing themselves by modifying protected-path policy or reviewer keys, and rejected duplicate trust-store identities before key selection.
- Removed the candidate worktree approver store from L3 authority, required a trusted Base or out-of-band public-key source, and bound Merge reviews to an immutable base SHA.
- Bound DEP and Rollback content plus the exact reviewed Head into Merge authorization, rejected non-audit post-review commits and protected-path rename bypasses, and made malformed stored expiry timestamps fail closed.
- Added a GitHub Actions bootstrap path for owner-controlled reviewer public keys without trusting candidate worktree state.
- Made Reviewer provisioning refuse Repo-local, symlinked, broadly readable, mismatched, or pre-existing key material; signing also refuses dirty worktrees, Builder identity reuse, wrong Base/digest, and non-audit descendants.

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
