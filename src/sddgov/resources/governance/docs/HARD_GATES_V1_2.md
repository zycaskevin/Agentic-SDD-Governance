# SDG v1.2 Hard Gates

This module closes three trust gaps without adding human approval to routine L0/L1 engineering.

## Fail-closed action classification

`sddgov autonomy evaluate` accepts only canonical categories. Every known action request must include an explicit `effects` object, using `{}` when no sensitive effect applies; omission, `null`, unknown flags, and false-valued flags fail closed. Unknown categories return `BLOCKED` with `requires_response: false`; the Agent must classify the action instead of asking the owner to approve uncertainty.

Production data deletion, irreversible migration, Secret change, permission-boundary change, real payment, and high-privilege Production operations always require L3. Routine categories may also declare sensitive effects. Any Production, destructive, irreversible, Secret, permission-boundary, payment, or high-privilege effect prevents an L0/L1 downgrade.

## Trusted L2 and L3 approval receipts

Caller-provided strings are not authority. A product owner signs L2 and L3 receipts outside the repository; only the public key is trusted by SDG.

For L2, the receipt follows `schemas/product-decision-approval-receipt.schema.json` and binds the decision ID, exact scope, a non-empty list of repository-relative assumption artifacts with their SHA-256 values, the canonical assumptions-list digest, the machine-readable `scope_or_assumptions_change` reopen condition, owner identity, validity window, and nonce. Import it with `sddgov decision import-product-approval`. On every reuse, SDG walks the signed artifact paths through retained non-symlink directory descriptors and recalculates their hashes; a missing, linked, moved, parent-replaced, or changed artifact reopens the decision. Unsupported free-form reopen prose fails closed. Caller-supplied digest or `reopen_condition_triggered` booleans are not authority. `decision record` is a deprecated fail-closed command and cannot create approval.

An L3 operation uses this sequence:

1. An external owner-controlled signer produces an Ed25519 envelope matching `schemas/operation-approval-receipt.schema.json`.
2. `.sddgov/trusted-approvers.json` is an auditable mirror only. Runtime authority comes only from `SDDGOV_TRUSTED_APPROVERS_FILE` when that file is outside the repository, root-owned, regular, single-linked, and not writable by group or other. A caller-selected Git SHA and a same-UID `0600` file are explicitly rejected because an Agent running as that user can create both.
3. The Agent runs `sddgov decision import-operation-approval signed-approval.json --path .`.
4. The signed receipt includes `operation_payload`: repository, project, environment, scope, exact category, target, non-secret parameters, and sensitive-effect flags. The outer receipt `scope` must equal the payload scope. Repository, project, and environment must also equal the root-controlled `/etc/sddgov/runtime-context.json`; caller-provided runtime labels are not authority. `sddgov autonomy evaluate request.json --path .` re-verifies the stored signed envelope and its digest under the decision lock, then compares the complete canonical payload SHA-256, operation ID, signer, expiry, and nonce. A successful result returns `authorized_operation_payload`; an executor must execute only that object. Editing `.sddgov/decisions.json` cannot create or expand L3 authority.
5. `CONTINUE` requires a separately running Broker to atomically consume the nonce across every clone and machine. Its fixed Unix socket is `/private/var/db/sddgov/approval-broker.sock` on macOS and `/run/sddgov/approval-broker.sock` on Linux; callers cannot override it. The socket must be root-owned, not world-writable, and located under an entirely root-owned, non-writable parent chain; only the trusted service creates or replaces it. The Agent sends one bounded canonical JSON line, then accepts only the exact `CONSUMED\n` response read to EOF within the size and timeout limits; normal stream fragmentation is allowed, while extra bytes fail closed. The Agent process itself must be non-root so root ownership remains a separate identity. This avoids executing a pathname from the Agent and works on both platforms without following macOS's `/var` symlink. A missing or untrusted context/Broker returns `BLOCKED` without another human approval prompt. Clone-local `decisions.json` is audit state, never the single-use authority ledger.

Private signing keys must never enter the repository, chat, DEP, Agent workspace, or CI. Provisioning the trusted Base/out-of-band public-key source or using an owner signing key is an Operational/L3 boundary and is intentionally outside this repository's autonomous workflow.

Both approval and review signatures use these canonical signing bytes: serialize only the inner `receipt` or `review` object with `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`, then UTF-8 encode it. Padded Base64 is required: Ed25519 public keys are 44 characters and signatures are 88 characters.

## Executable Merge policy

`sddgov merge verify . --base-ref <exact-base>` executes the Merge contract:

- clean exact-HEAD worktree;
- executable change digest, immutable `base_sha`, and exact reviewed `head_sha`;
- repository Local Green Gate;
- strict Proof-phase DEP for L1-L3;
- zero Redaction blockers and no tracked `private/raw` Evidence;
- structured rollback record with `rollback_version`, explicit `target`, executable `command`, and `verify` fields;
- trusted-reviewer Ed25519 receipt when a protected path changed.

The GitHub Governance workflow uses `pull_request_target`, so GitHub loads the workflow from the trusted Base rather than the PR. It checks out the candidate under `candidate/` as untrusted data and the exact Base under `trusted-verifier/`, installs only hash-locked dependencies from `requirements-governance.lock`, and runs it with `PYTHONPATH` pinned to `trusted-verifier/src`. Every external Action is pinned to a full commit SHA. Hosted verification passes `--skip-local-checks`, because candidate-defined Local Green commands would execute untrusted PR code; those checks belong in a separate least-privilege workflow. No candidate script, build hook, or test command runs inside this privileged governance job.

Configure the Governance result as a required check in repository rulesets; a workflow file alone cannot prevent an administrator from bypassing GitHub controls. The first hardening PR is still judged by the previously installed Base workflow, so it also requires fresh independent review before Merge. Later PRs receive the separated verifier automatically.

The Merge gate follows `schemas/merge-gate.schema.json`. `change_digest` excludes only `.sddgov/merge-gate.json` and `.sddgov/reviews/`. DEP and Rollback content remains inside the digest, so it cannot change after review. The recorded `head_sha` is the exact reviewed commit; current HEAD may descend from it only through commits whose paths are limited to those two audit-receipt locations.

Calculate `base_sha`, reviewed `head_sha`, and the executable digest with `sddgov merge digest . --base-ref <exact-base>`. Place them in the Merge gate, then calculate the review metadata binding with `sddgov merge gate-digest .`. Place both digest values in the independent Review receipt. Commit only the gate and receipt afterward, then run `sddgov merge verify`.

The Review receipt follows `schemas/protected-review-receipt.schema.json` and must live under `.sddgov/reviews/`. Its signer must be active in the reviewer store from the trusted base revision, the reviewer must differ from the Builder, and the receipt must approve both the exact executable `change_digest` and `gate_metadata_digest` while unexpired. The metadata digest is SHA-256 over canonical JSON containing `schema_version`, `base_sha`, `head_sha`, `risk_level`, `builder_id`, `change_digest`, `deps`, and `rollback_path`; changing the base, reviewed Head, risk, or Evidence requirements after review therefore invalidates the receipt. A Builder-authored `reviewer_id` string is not review authority.

Protected-path policy and Reviewer authority are read from the trusted base revision first. A populated Base store is authoritative even when every key is revoked; an external variable can never reactivate a revoked Reviewer. External bootstrap is allowed only when the Base store exists with the exact initial empty list. The bundled GitHub workflow materializes that public-key-only bootstrap file from `SDDGOV_TRUSTED_REVIEWERS_JSON` in runner temporary storage. Configure it and the required-check ruleset as a one-time Operational action before converting the bootstrap PR from Draft.

The independent Reviewer performs this bootstrap without asking the product owner for a key. On its separate host and clean checkout it runs `sddgov reviewer bootstrap`, registers the output of `sddgov reviewer export-trust` directly as `SDDGOV_TRUSTED_REVIEWERS_JSON`, completes its independent checks, and runs `sddgov reviewer sign`. The private key remains owner-only and Repo-external; the signed public receipt is the only key-related artifact committed. See the on-demand `references/independent-reviewer.md` module.

An empty `.sddgov/trusted-approvers.json` is not a Merge failure. It is a safe default that prevents future L3 operations until a separate owner-controlled L3 identity is deliberately provisioned.

Raw Evidence is checked across every commit in `base_ref..HEAD`, not only the final tree. Adding and later deleting `private/raw/` data still fails the gate because the sensitive bytes remain in Git history.

## Evidence integrity recomputation

Strict DEP verification does not trust `manifest.json` assertions. DEP creation walks and retains the Evidence-root parent chain; Collector input and custom attachment output retain their complete parent chains; DEP operations retain the opened DEP and artifact-zone descriptors. Files are opened relative to those descriptors without following symlinks, and verification recomputes normalized path, file type, link count, byte size, SHA-256, immutable source suffix, and detected media type. Collection, redaction, verification, attachment, and manifest/report/summary writes keep the relevant verified descriptors through final reads, same-directory temporary writes, and atomic replacement. `attach` performs strict verification from one immutable in-memory summary/manifest snapshot and uses only that verified snapshot to generate output. A framed SHA-256 of those exact control bytes is embedded in the attachment and its default content-addressed filename. Output is staged under a unique private name, the control identities are checked once more as the operation's linearization point, and publish uses atomic no-clobber semantics. A swap before that point fails closed and removes only staging; an update after that point starts a different control generation and cannot change what the already generated attachment proves. A later destination writer wins and is never deleted or overwritten. Base, source, DEP, zone, or output parent replacement still fails closed. It rejects missing files, unregistered extras, hardlinks, duplicate manifest paths, duplicate collector destinations, path escape, symlinked DEP zones/files/control documents, and altered redaction associations. Every raw row must appear exactly once in either `report.files.source` or `report.blocked.file`; every shareable row must appear exactly once as an output. A `browser-har` collector or detected HAR remains blocked regardless of its label or suffix. Unknown or binary types remain blocked rather than relying on filename-controlled generic text redaction.

Portable PR verification may omit local `private/raw` bytes. It validates the complete raw metadata/report set relationship and fully recalculates every shareable artifact, but it cannot prove that omitted raw bytes ever existed or were honestly collected. Full local strict verification is required before attachment; stronger remote provenance requires a future independent control-plane signature over the locally verified manifest/report digest.

## Remaining trust boundary

SDG can fail closed on malformed or missing inputs, but it cannot make an Agent's operating-system account less privileged than it already is. Production credentials, owner private keys, GitHub branch protection, and deployment permission remain external controls.
