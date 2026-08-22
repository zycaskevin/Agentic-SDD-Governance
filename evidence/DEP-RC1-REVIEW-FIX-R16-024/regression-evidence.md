# Regression Evidence

## Regression test added or strengthened

- Assert the fixed Darwin staging pathname is no more than 103 encoded bytes.
- Run every real AF_UNIX test under a bounded `/tmp/sgb-*` root.
- Require native CI to build the wheel with both locks, install into a fresh
  consumer, clear checkout provenance, and assert `sddgov` is wheel-installed.
- Fresh-wheel smoke uses a short POSIX root and repeats Broker health/cleanup.

## Related tests executed

The isolated dual-lock environment passed 381 tests. Real Linux source tests
passed seven semantics plus the Darwin boundary (one expected installed-wheel
provenance skip). A separate installed-wheel run passed all eight tests. Validate
and CI verify passed; hosted Linux/Darwin Green remains required before signing.

## Unaffected paths sampled

Autonomy receipts, DEP lifecycle, redaction, service mirrors, release locks,
build/Twine, offline bundle, Codex/Hermes Doctor, demo, exact-tree rollback, and
229 Base tests passed. The R15 Evidence package is preserved as predecessor audit.
