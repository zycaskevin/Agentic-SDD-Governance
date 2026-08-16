# Autonomous Development and Escalation

Default to `CONTINUE`. Before stopping, evaluate in order: Repository/SDD, Decision/ADR, Tests/CI/Tools, safe reversible L0/L1 decision, then whether only one Work Package is blocked. Only unresolved L2, concrete L3, Operational Action, or Necessary UAT may produce `ACTION REQUIRED`.

Never ask for approval to create an Issue, Branch, Commit, feature-branch Push, PR, Review, test, retry, integrity check, or L0/L1 Merge after required gates pass. Never ask a human to copy, paste, calculate, compare, or approve SHA-256.

Use:

```bash
sddgov autonomy evaluate request.json --path .
sddgov checkpoint --summary "..." --next-work-package WP-002
sddgov artifact lock dist/package.whl --release release-X --output release.lock
sddgov artifact verify dist/package.whl --lock release.lock
sddgov decision import-product-approval signed-product-decision.json --path .
sddgov decision import-operation-approval signed-approval.json --path .
sddgov merge verify . --base-ref <exact-base>
```

Every known action request must include an explicit `effects` object. Use `{}` only after classification confirms that no Production, destructive, irreversible, Secret, permission-boundary, real-payment, or high-privilege effect applies.

Routine L0/L1 requests use an exact authority-free envelope containing only risk, category, and explicit empty effects, plus the two bounded booleans defined for integrity/uncertainty routes. They must not carry `approval_id`, `operation_id`, `operation_payload`, `decision_id`, `decision_scope`, `decision_package`, a concrete target, arbitrary parameters, or any unknown nested field. Free text is never proof that an executable action is low risk; route every concrete action through its separately closed typed executor contract and fail closed instead of accepting the caller label.

Import an approved L2 decision only through a separate-identity trust root. The signed receipt lists exact assumption artifacts; SDG recalculates their current bytes on every reuse and never trusts a caller freshness boolean. L3 binds repository, project, environment, scope, category, target, parameters, and effects. Repository/project/environment must match root-controlled `/etc/sddgov/runtime-context.json`, outer and inner scope must match, and the Agent process must be non-root. It reaches `CONTINUE` only after the root-provisioned Unix service at `/private/var/db/sddgov/approval-broker.sock` on macOS or `/run/sddgov/approval-broker.sock` on Linux atomically consumes the signed nonce across clones; callers cannot override this platform path, and the Agent executes only the returned `authorized_operation_payload`. A missing context or Broker is machine-actionable `BLOCKED`, not another approval request. A previous product decision or caller string never authorizes a new L3 operation.

Unknown categories and dangerous L0/L1 downgrades fail closed for machine reclassification. Before Merge, execute the Merge verifier; do not treat `policies/merge-policy.yaml` as self-enforcing documentation.

Operational Actions and Necessary UAT cannot reuse a generic Product Decision receipt. Persist an Operational Action with a stable owner, exact scope, request digest, and expiry through `sddgov external-action`; repeating the same bounded request must reuse the durable record rather than emit another owner prompt. Unrelated Work Packages continue while the action is pending.

For Production, L0 is invalid. A routine reversible L1 deploy is autonomous only with recorded Baseline authorization and every guard in `policies/autonomy-policy.json`. Missing evidence blocks and triggers investigation; it does not become an approval request by itself.

Sub-agents report uncertainty to the Main Agent. The Main Agent performs lookup, evidence gathering, classification, and L0/L1 resolution before any owner escalation.
