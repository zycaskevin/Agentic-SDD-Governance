# SDG v1.2 Hard Gates

This module closes three trust gaps without adding human approval to routine L0/L1 engineering.

## Fail-closed action classification

`sddgov autonomy evaluate` accepts only canonical categories. Unknown categories return `BLOCKED` with `requires_response: false`; the Agent must classify the action instead of asking the owner to approve uncertainty.

Production data deletion, irreversible migration, Secret change, permission-boundary change, real payment, and high-privilege Production operations always require L3. Routine categories may also declare sensitive effects. Any Production, destructive, irreversible, Secret, permission-boundary, payment, or high-privilege effect prevents an L0/L1 downgrade.

## Trusted L3 approval receipts

Caller-provided strings are not authority. `decision authorize-operation` and the separate consume command are removed. An L3 operation uses this sequence:

1. An external owner-controlled signer produces an Ed25519 envelope matching `schemas/operation-approval-receipt.schema.json`.
2. The repository contains only active public keys in `.sddgov/trusted-approvers.json`, matching `schemas/trusted-approvers.schema.json`.
3. The Agent runs `sddgov decision import-operation-approval signed-approval.json --path .`.
4. `sddgov autonomy evaluate request.json --path .` verifies exact operation ID, signer, expiry, nonce, and unused state.
5. The first `CONTINUE` atomically consumes the receipt. Reuse returns `ACTION REQUIRED`; concurrent evaluation permits at most one consumer.

Private signing keys must never enter the repository, chat, DEP, Agent workspace, or CI. Provisioning or using an owner signing key is an Operational/L3 boundary and is intentionally outside this repository's autonomous workflow.

## Executable Merge policy

`sddgov merge verify . --base-ref <exact-base>` executes the Merge contract:

- clean exact-HEAD worktree;
- executable change digest bound to the base;
- repository Local Green Gate;
- strict Proof-phase DEP for L1-L3;
- zero Redaction blockers and no tracked `private/raw` Evidence;
- completed rollback record;
- trusted-reviewer Ed25519 receipt when a protected path changed.

The GitHub Governance workflow fetches full history and runs this command for non-Draft PRs and `main` pushes. Configure it as a required check in repository rulesets; a workflow file alone cannot prevent an administrator from bypassing GitHub controls.

The Merge gate follows `schemas/merge-gate.schema.json`. `change_digest` excludes only audit receipts (`.sddgov/merge-gate.json`, `.sddgov/reviews/`, and `evidence/`) so a review receipt may be added after reviewing the executable change without invalidating that review.

Calculate it with `sddgov merge digest . --base-ref <exact-base>`, place that value in the Merge gate and independent Review receipt, then run `sddgov merge verify`.

The Review receipt follows `schemas/protected-review-receipt.schema.json` and must live under `.sddgov/reviews/`. Its signer must be active in `.sddgov/trusted-reviewers.json`, the reviewer must differ from the Builder, and the receipt must approve the exact executable change while unexpired. A Builder-authored `reviewer_id` string is not review authority.

## Remaining trust boundary

SDG can fail closed on malformed or missing inputs, but it cannot make an Agent's operating-system account less privileged than it already is. Production credentials, owner private keys, GitHub branch protection, and deployment permission remain external controls.
