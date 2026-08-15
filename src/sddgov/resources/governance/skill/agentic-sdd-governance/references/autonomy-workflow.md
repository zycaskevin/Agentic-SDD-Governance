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

Import an approved L2 decision only through a separate-identity trust root. The signed receipt lists exact assumption artifacts; SDG recalculates their current bytes on every reuse and never trusts a caller freshness boolean. L3 binds repository, project, environment, scope, category, target, parameters, and effects. Repository/project/environment must match root-controlled `/etc/sddgov/runtime-context.json`, outer and inner scope must match, and the Agent process must be non-root. It reaches `CONTINUE` only after a descriptor-pinned root-owned external nonce broker atomically consumes the signed nonce across clones; execute only the returned `authorized_operation_payload`. A missing context or broker is machine-actionable `BLOCKED`, not another approval request. A previous product decision or caller string never authorizes a new L3 operation.

Unknown categories and dangerous L0/L1 downgrades fail closed for machine reclassification. Before Merge, execute the Merge verifier; do not treat `policies/merge-policy.yaml` as self-enforcing documentation.

For Production, L0 is invalid. A routine reversible L1 deploy is autonomous only with recorded Baseline authorization and every guard in `policies/autonomy-policy.json`. Missing evidence blocks and triggers investigation; it does not become an approval request by itself.

Sub-agents report uncertainty to the Main Agent. The Main Agent performs lookup, evidence gathering, classification, and L0/L1 resolution before any owner escalation.
