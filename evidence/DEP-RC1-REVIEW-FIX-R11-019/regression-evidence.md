# Regression Evidence

## Regression test added or strengthened

Added or strengthened regression coverage for fixed Linux/macOS Broker groups, root-owned exact-`0660` readiness, ownership-preserving socket setup, wrong-group rejection, 64 MiB active-ledger scan/append limits, exact discovered workflow exemptions and write exceptions, final-component-only release directory creation, primary cleanup error preservation with chained cleanup diagnostics, launchd throttling, directory pending-generation diagnostics, redaction rollback after source identity failure, platform support wording, package version derivation, and R6 proof/falsification accuracy.

## Related tests executed

Focused Red: 12 tests produced six failures and nine errors before the changes. Final Local Green: 346 tests passed with two explicit skips and repository validation passed. Package proof validates source first, then builds the RC1 wheel/sdist, passes Twine, assembles an 11-dependency-wheel offline bundle, and passes fresh-wheel Codex/Hermes Doctor/Validate/quick-demo checks. Final rollback proof passes 229 Base tests with two explicit skips plus Base build/Twine/fresh install.

## Unaffected paths sampled

Autonomy classification and signed receipt tests, CI Cost Guard semantics, transactional/symlink/hardlink/FIFO Evidence paths, streaming redaction boundaries, canonical/package/install parity, synthetic pilot, and exact-tree Merge Gate tests all remain Green. The two current/Base skips retain exact reasons: sandbox Unix socket creation is forbidden, and the historical PR #14 rollback commit is absent from this local clone.
