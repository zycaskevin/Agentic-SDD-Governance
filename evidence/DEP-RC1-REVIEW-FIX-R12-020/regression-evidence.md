# Regression Evidence

## Regression test added or strengthened

Added or strengthened coverage for delayed trailing Broker records, EOF-bound single-record framing, handler rejection before ledger validation/consumption, capacity rejection before `_scan_locked`, 80 percent startup telemetry, fixed trust authority and caller override rejection, offline Linux/x86_64 guards, launchd `_sddgov` identity and integer umask, executable/version preflight, bounded newsyslog parity, pinned Python in every publication job, runtime lock separation, public resource access, exempt-workflow exception rejection, and clean non-POSIX/Git test skips. Repository contracts also prevent the corrected historical proof text from regressing.

## Related tests executed

Focused Red: 13 tests produced 12 failures and four errors before the changes. Final Local Green: 357 tests passed with two explicit skips. Source validation passed. Package proof validates source first, builds the RC1 wheel/sdist, passes Twine, assembles a ten-dependency-wheel locked offline bundle, and passes fresh-wheel Codex/Hermes Doctor/Validate/quick-demo checks. Final rollback proof passes 229 Base tests with two explicit skips plus Base build/Twine/fresh install.

## Unaffected paths sampled

Autonomy classification and signed receipts, CI Cost Guard workflow semantics, transactional/symlink/hardlink/FIFO Evidence paths, streaming redaction boundaries, release descriptor validation, canonical/package/install parity, synthetic pilot, exact-tree Merge Gate, and all historical portable DEP verification remain Green. The two current/Base skips retain explicit environmental/history reasons rather than masking failures.
