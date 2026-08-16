# Changelog

## 0.2.0-experimental.8 — 2026-08-16 security hardening (unreleased)

### Security

- Pre-authorize minimum routine review submission for an already-configured Reviewer: committed public PR changes and public repository instructions may be reviewed without a per-PR owner prompt, while Private Repo content without a recorded pair decision, Secrets, raw Evidence, real user data, new vendors/access, and new cost remain fail-closed.
- Restrict every autonomy category and risk level to one closed request schema before decision or approval reuse; L0/L1 stays targetless and parameterless, product L2 reuse rejects foreign L3 fields and any new nested Decision Package, and product receipts cannot authorize Operational Action or Necessary UAT categories.
- Constrain L2 reopen behavior to the machine-readable `scope_or_assumptions_change` contract and retain non-symlink repository directory descriptors while recalculating assumption artifacts.
- Replace CI workflow regex checks with YAML 1.2 duplicate-key-rejecting semantic validation for triggers, exact non-bypassable Draft conditions, valid runners, concurrency, permissions, and bounded job timeouts; read every workflow through retained non-symlink directory descriptors.
- Recheck the exact verified Evidence artifact generation immediately before attachment publication; reject intermediate symlinks, nonblocking-open non-regular inputs, pending attachment residue, and interrupted staging.
- Use generation-bound no-clobber control publication, clean only transaction-owned collect/redact outputs on failure, preserve later writers, replace free-form rollback shell strings with an allowlisted declarative v2 contract, and protect the complete trusted source/workflow/dependency surface including Agent-loaded installed governance copies.
- Add a non-executing, exact-field legacy rollback v1 compatibility bridge so the experimental.7 trusted Base can validate the v2 migration PR; wrappers, chaining, alternate commands, duplicates, extra fields, and placeholders remain rejected, and all new records use declarative v2.
- Bind the temporary v1 bridge to the exact experimental.7 Base and migration DEP, reject standalone unknown text, and require every v1/v2 rollback ref to resolve to a full immutable commit inside the reviewed candidate range.
- Require the selected rollback ref to be a single-parent implementation-only commit whose inverse applies conflict-free at the exact reviewed Head, proven with a non-executing Git tree simulation before Merge.
- Persist one owner-, scope-, TTL-, and digest-bound Operational Action record so repeated calls do not emit duplicate prompts.
- Add known provider-credential detectors while preserving clean zero-match text, and upgrade the trusted verifier dependency line to hash-locked `cryptography==50.0.0`.

### Evidence

- Added `DEP-SDG-SECURITY-HARDENING-EXP8-001`, second-round `DEP-SDG-SECURITY-HARDENING-EXP8-R2-002`, third-round authority-envelope `DEP-SDG-SECURITY-HARDENING-EXP8-R3-003`, protected-inventory `DEP-SDG-SECURITY-HARDENING-EXP8-R3-PROTECTED-004`, nested-authority `DEP-SDG-SECURITY-HARDENING-EXP8-R4-AUTH-005`, rollback-contract DEPs R5-R7, and permanent defensive regression tests for Issue #11.
- This entry records implemented local work only; independent review, exact Merge verification, GitHub-hosted proof, and release publication remain separate gates.

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
- Bound Evidence to Collector identity, immutable source suffix, and detected media type, and retained verified base/source/DEP/zone/output directory descriptors through DEP creation, collection, redaction, strict verification, attachment, and atomic control-document writes. Attachment generation consumes the exact in-memory summary/manifest snapshot that strict verification checked, records its framed SHA-256 generation digest in both content and default filename, stages before the final control check, and uses atomic no-clobber publish so concurrent control generations cannot contaminate each other or overwrite a later writer.
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
