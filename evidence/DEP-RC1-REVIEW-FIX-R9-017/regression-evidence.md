# Regression Evidence

## Regression test added or strengthened

Added deterministic tests for retained input/output directory generations, nested dependency-wheel rejection, output-parent failure reports, pre-publication oversized Evidence rejection, absent-workflow permission exceptions, strict repository slugs, bounded 403/429 retry and HTTPError close, common benchmark error schema and Git timeout, English README parity, fetch-before-branch rollback instructions, recursive nested DEP artifact detection, exact systemd hardening/mirror parity, and cleanup ownership races.

## Related tests executed

The focused review suite passed after the fix. Current Local Gate passed 323 tests with two explicit environment skips plus repository validation. Doctor, validate, and CI verification passed. Isolated build and Twine passed; the locked ten-wheel offline bundle and fresh-wheel Codex/Hermes setup, doctor, validate, and quick demo passed. The actual Rollback v3 drill passed Base doctor/validate, 229 Base tests with two explicit skips, Base build/Twine/version, raw exact-Base equality, and post-reconcile semantic equality.

## Unaffected paths sampled

Autonomy signatures and nonce semantics, reviewer and merge verification, installer lifecycle, demo, synthetic pilot, schema validation, package metadata, canonical/package/installed resource parity, and all tracked predecessor Proof DEP packages were exercised by the full Local Gate. No external registry, service, credential, or Production state changed.
