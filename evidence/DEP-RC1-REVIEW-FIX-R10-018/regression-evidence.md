# Regression Evidence

## Regression test added or strengthened

Added or strengthened regression coverage for permanent versus rate-limit 403, bounded Evidence report probing, valid JSON media labels, manifest 1.0/1.1 compatibility, bounded Broker ledger records, safe Broker error text, bounded exponential accept retry/reset, exact-tag release guard, TestPyPI polling, source-resource parity, Python version guidance, script protection, demo interpreter selection, package lock, scaled benchmark timeout, Work Package authority/sequence, and untracked rollback residue.

## Related tests executed

Focused review suite: 144 tests passed before the manifest compatibility follow-up. Final Local Green: 333 tests passed with two explicit skips and repository validation passed. Package proof validates source first, then builds RC1 wheel/sdist, passes Twine, assembles an 11-dependency-wheel offline bundle, and passes fresh-wheel Codex/Hermes Doctor/Validate/quick-demo checks. Final rollback proof passes 229 Base tests with two explicit skips plus Base build/Twine/fresh install.

## Unaffected paths sampled

Autonomy classification and signed receipt tests, CI Cost Guard, transactional/symlink/hardlink/FIFO Evidence paths, redaction cross-chunk behavior, canonical/package/install parity, synthetic pilot, and exact-tree Merge Gate tests all remained Green. The two current/Base skips retain exact reasons: sandbox Unix socket creation is forbidden, and the historical PR #14 rollback commit is absent from this local clone.
