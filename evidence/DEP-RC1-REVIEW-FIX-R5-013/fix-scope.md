# Fix Scope

## Smallest sufficient change

Preserve the RC1 architecture while fixing verified R4 review gaps: require the complete exact-tag environment inventory; centralize expanded, safe-name, single-link release file checks; add installed managed-tree validation to the fresh wheel; frame Broker records at the first newline; use portable post-bind path ownership/mode changes with inode/type/uid/gid/mode readback; fail closed on suspicious partial private-key delimiters; bind source demos to checkout `src`; clarify ledger creation, launchd stale-socket recovery, systemd group coupling, and expiry-gated ledger epoch rollover; and strengthen the focused tests.

## Files or components in scope

Release scripts and tests; `src/sddgov/{broker,cli,redaction}.py`; canonical, packaged, and installed protected-file policy; canonical/package/install Broker services and L3 runbook; English and Traditional Chinese demo onboarding; `demo/run.sh`; the current installed manifest; Work Package Evidence binding; and targeted Broker, CI, redaction, release, demo, and repository-contract tests.

## Explicit non-scope

No action-classification change, signing/key generation, real trusted approver provisioning, root Broker installation, GitHub environment/ruleset mutation, TestPyPI/PyPI/GitHub publication, tag, protected-branch merge, affected-path rollback proof, production mock, thread reply, or review-thread resolution. No historical R4 Evidence is rewritten; R5 carries a new authoritative review mapping.

## Blast radius

Local developer, package-release preflight, and Broker operational behavior. Changes remain fail-closed: incomplete policy pages reject; release files gain stricter safe-name checks; suspicious fragmented delimiters abort transactionally; the Broker preserves fixed paths and inode/type/ownership checks; ledger rollover requires complete receipt expiry; and exact Base-tree rollback remains unchanged.
