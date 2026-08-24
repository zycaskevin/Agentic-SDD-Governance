# Root Cause Hypothesis

## Hypothesis

R27 made the timeout field structurally and manually mandatory even though
existing user-owned CI contracts are intentionally preserved during upgrades.
The runtime therefore had no compatibility path. Independently, the workflow
inspector gated only the missing-concurrency branch on `require_concurrency`,
and the benchmark supplied the scaled timeout to only the first two expensive
Git calls.

## Supporting evidence

- Exact CodeRabbit review `5004444722` reported all three boundaries.
- A legacy contract missing only the timeout is retained unchanged by
  `setup-agent --force` and then rejected by R27 `ci verify`.
- `_inspect_workflow` receives empty controls for an exemption but the old
  non-empty group check runs unconditionally.
- The benchmark source shows later `_git` calls using the fixed default rather
  than `setup_timeout`.

## Contradicting evidence

The current repository's explicit timeout value already passes, and hosted
Ubuntu/macOS runs were Green. This narrows the failure to compatibility,
exemption completeness, and large-fixture reliability rather than the core
timeout enforcement or rollback proof.

## Falsification test

Allow omission only for schema `1.0`, apply the same bounded 600-second value in
validation and execution, keep explicit invalid values rejected, gate both
concurrency checks on the control, and assert every fixture `_git` call receives
the scaled timeout. If those tests pass while the full suite and exact-tree
rollback remain Green, the hypothesis is supported.

## Conclusion

Confirmed. The smallest fix is a documented schema-1.0 runtime fallback plus
complete control gating and consistent timeout propagation; no Owner authority,
decision assumption, or exact-tree proof needs to change.
