# CI Cost Guard Route

Read `docs/CI_COST_GUARD.md` under the Governance Root when work creates, modifies, reruns, or diagnoses CI.

Before Push:

1. Read `.sddgov/ci-cost-guard.json`.
2. Run `sddgov ci verify .`.
3. Run `sddgov ci local-gate .`.
4. Batch the bounded Work Package into one reviewable revision.
5. Do not rerun the same revision unless Evidence proves a transient failure.

When the contract sets `hosted.post_merge_verification` to `manual_only`, reject automatic `push` triggers even for exempt workflows. The Ready PR check is the Work Package run; a Release verification is an explicit `workflow_dispatch`, not a hidden second run after Merge. A schema `1.0` contract that omits this new field retains legacy `automatic` behavior until it is explicitly upgraded.

`sddgov ci verify` reads the contract and workflow tree through retained non-symlink directory descriptors, accepts only single-linked regular YAML files, and parses YAML 1.2 data with duplicate-key rejection. Comments or quoted examples do not satisfy a guard; Draft skipping must be the exact required condition rather than one branch of an always-true expression; runners, concurrency groups, permissions, event filters, and timeouts are validated structurally.

Use the DEP debugging route for a non-transient CI failure. CI optimization is L1 only while acceptance criteria and required proof remain unchanged. Billing, paid runners, and self-hosted runner installation remain L3 external actions.
