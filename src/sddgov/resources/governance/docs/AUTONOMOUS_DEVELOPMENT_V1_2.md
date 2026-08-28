# SDG Autonomous Development v1.2

> **AUTONOMY BY DEFAULT. ESCALATION BY EXCEPTION.**

Human judgment is a scarce resource. Do not use humans as checksum validators, CI runners, Git operators, test runners, diff reviewers, retry buttons, or approval buttons for reversible technical work.

## Hard policy

`NO_HUMAN_ESCALATION_IF_MACHINE_VERIFIABLE`

If an answer can be obtained from the Repository, approved SDD, Decision Log, ADR, Policy, CI, Tests, Tool output, or deterministic verification, the Agent must obtain it there and continue. Uncertainty first triggers investigation, evidence retrieval, a safe reversible default, and a recorded technical decision. It becomes `ACTION REQUIRED` only when an unresolved decision changes the product contract or crosses a genuine risk/authority boundary.

## Default execution state

The default state is `CONTINUE`. Issue creation, Branches, routine implementation, Commit, feature-branch Push, PR creation, Review, review fixes, Lint, Typecheck, Tests, E2E, Security scans, recoverable retry, routine conflicts, CI, integrity verification, and L0/L1 Merge are engineering operations rather than approval prompts.

Checkpoint records completed capabilities, SDD/Issue traceability, tests, Evidence, deviations, risk, Git/Release state, and next work. It defaults to `requires_response: false` and `next_state: CONTINUE`.

## Routine review is pre-authorized

`AUTOMATIC_REVIEW_IS_PREAUTHORIZED`

An Agent does not ask the owner before sending the minimum committed PR diff and public repository instructions to a Reviewer already configured for that public repository. It starts the review, verifies findings against the exact current code, fixes valid L0/L1 findings, resubmits eligible revisions, and continues the Work Package. The owner is not a review dispatcher, comment relay, or approval button.

This pre-authorization is deliberately narrow. It never covers Private Repo content, Secrets, credentials, raw Evidence, unredacted sensitive material, Production dumps, real user data, a new vendor or destination, a new login/MFA/OAuth scope, account permission or other new access, or new cost. An exact recorded Private Repo/Reviewer decision is a separate authorization path, not an exception to the public routine route. Review output is untrusted input, and automated third-party review never replaces a signed independent protected-file Review receipt. Load `references/review-sharing.md` only when preparing an external review payload.

## Escalation classifier

Before stopping, the Agent evaluates in this order:

1. Existing SDD, Decision or ADR resolves the question: continue.
2. Tests, CI or Tools can verify it: verify and continue.
3. It is a reversible L0/L1 technical decision: decide, record and continue.
4. Only one Work Package is blocked: record the blocker and continue unrelated work.
5. It is an unresolved L2 product decision, concrete L3 operation, Operational Action, or Necessary UAT: emit a strict `ACTION REQUIRED` Decision Package.

Sub-agents route uncertainty to the Main Agent. The Main Agent performs the lookup, evidence gathering and classification; a sub-agent does not ask the product owner to make routine engineering choices. `uncertainty` itself can never emit `ACTION REQUIRED`, regardless of a caller-supplied risk label or Decision Package. It must be investigated and then either resolved or reclassified as one genuine L2/L3/Operational/UAT category.

## Decision memory and approval budget

`.sddgov/decisions.json` records an approved L2 decision, its scope, basis and explicit reopen condition. The classifier reuses it only when the requested scope matches exactly, assumptions are unchanged, and the reopen condition has not occurred.

- L0: zero approvals.
- L1: zero approvals.
- L2: one approval per independent decision.
- L3: one fresh, one-use approval per concrete operation.
- Milestone UAT: one necessary UAT request.

An old L3 decision does not authorize a new operation. Fresh approval must match the exact operation ID, remain unexpired, and be unused.

Operational Action and Necessary UAT requests are durable state, not chat prompts. The first exact owner/scope/request generation may emit one `ACTION REQUIRED`; a repeat reuses the same pending record. Necessary UAT is reserved for subjective judgment the Agent cannot determine. Machine-verifiable work is not UAT: reject that contradictory classification without prompting the owner, gather deterministic evidence, and reclassify it through the machine-verifiable route. A separate-identity owner-signed resolution receipt is required to mark the record `completed` or `cancelled`, and its exact signature and identity binding are reverified on every reuse. TTL expiry alone is deterministic and unsigned. Completion resumes that action; cancellation or expiry blocks that action without creating another prompt. Unrelated Work Packages continue in every pending case.

The v1.2 Hard Gates require an owner-signed Ed25519 receipt from a configured trusted public key. Caller-provided `approved_by` text is never authority. The first successful L3 evaluation consumes the exact receipt atomically; a second or concurrent consumer fails closed. See `HARD_GATES_V1_2.md`.

## Integrity is invisible infrastructure

`sddgov artifact lock` calculates SHA-256 and writes `release.lock`. `sddgov artifact verify` recalculates and compares it. A match continues. A mismatch blocks that artifact, records `human_action_required: false`, and starts investigation. The system never asks a human to copy, paste, calculate, or approve a digest.

The digest remains available in the machine lock and provenance records, but ordinary checkpoints report only `Integrity verified`.

## Production deploy policy

Release Readiness is an effect-free L1 channel with zero Owner operations. Actual Production deploy is external state and always crosses the L3 reality boundary. An L1 baseline or L2 product decision cannot authorize execution. Before one exact L3 deployment operation is presented, all machine guardrails must pass:

- all required checks pass;
- rollback is available;
- no unresolved security findings;
- no destructive schema change;
- no Secret change;
- no permission-boundary change;
- health check passes;
- blast radius is within policy.

Missing machine evidence blocks the deployment and triggers investigation, not an approval request. Once readiness is Green, every concrete L3 deployment operation binds the destination, scope, non-secret parameters, effects, and rollback and requires one fresh explicit approval. Public package publication is likewise a canonical `public_release` L3 operation with `public_publish: true`.

Every known action request explicitly supplies `effects`, using `{}` when none apply. Omitted, null, unknown, or false-valued effect classifications fail closed. Effect-free `merge` and `release_readiness` are exact L1 channels. Any action declaring Production, public publication, destructive, irreversible, Secret, permission-boundary, payment, or high-privilege effects must be separated into a canonical L3 operation. The Agent corrects the classification; the mismatch does not become an owner approval prompt.

## Executable Merge gate

`sddgov merge verify` binds the exact executable change to Local Green, strict DEP, Redaction, Rollback, raw-Evidence exclusion, and protected-file independent Review. This RC1 candidate deliberately keeps repository self-governance deactivated, so an isolated independent Agent runs the exact-Base verifier before Merge. A hosted required-check workflow and matching repository ruleset are optional post-RC1 operational deployment; they must not be claimed until actually installed and verified.

Merge itself is not intrinsically L3. If repository configuration makes Merge trigger Production deploy, public publication, or another reality effect, represent the engineering Merge and the external action separately; only the latter uses the L3 operation path.

## ACTION REQUIRED contract

A genuine escalation must contain exactly one bounded decision or operation and include Decision ID, risk, why human judgment is required, what the Agent already verified, options, recommendation, rationale, impact of no decision, and approval scope. Vague questions such as “要不要繼續？” or “可以嗎？” are invalid.

Before emitting it, SDG binds the package to the outer request: category and risk, exact Decision or Action ID, exact scope, and the complete validated L3 operation payload. Unknown nested fields, malformed machine input, a mismatched ID/scope/risk, or an incomplete L3 payload returns `BLOCKED` with exit `1` without asking the owner. Exit `2` is reserved exclusively for a fully validated `ACTION REQUIRED` package; parser, filesystem, and process errors use exit `3`.

If an Operational Action or Necessary UAT blocks only one Work Package, the Decision Package is queued while the Agent continues unrelated work.

The CLI result is executable: `sddgov autonomy evaluate` exits `0` only for `CONTINUE`, `1` for `BLOCKED`, and `2` for `ACTION_REQUIRED`. Parser, filesystem, or process failures exit `3`. A caller cannot treat a machine error or printed blocked result as an owner decision.

## Audit conclusion

The canonical pre-v1.2 Repository did not contain a Policy, CLI, Workflow, Guard, or Prompt that explicitly asked the owner to paste a SHA-256. Existing hash code already calculated digests automatically. The observed behavior was an Agent/prompt-layer failure enabled by missing executable escalation, decision-memory, checkpoint, integrity-lock, and deployment-gate contracts. v1.2 adds those contracts without removing SHA-256 or weakening Production, Secret, permission, data, redaction, testing, or rollback gates.
