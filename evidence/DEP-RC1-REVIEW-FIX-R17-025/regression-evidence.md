# Regression Evidence

## Regression test added or strengthened

- Both public sanitizers reject bare home/temp roots and complete
  space-containing descendant paths while preserving prefix siblings.
- Both release CLIs reject a report symlink and prove its target byte content is
  unchanged; safe nested parent creation remains supported.
- Bundle preparation catches `zlib.error` and emits only sanitized JSON.
- Repository contracts bind R17 as authoritative, assert its L1 text, and prove
  no unsigned decision was added to manufacture an L2 authorization.

## Related tests executed

The dual hash-locked Python 3.12 environment passed 385 tests with 12 local
AF_UNIX sandbox skips. Repository Validate, CI verify, and Local Gate passed.
The focused release bundle suite passed 23 tests, including all new security
regressions.

## Unaffected paths sampled

Autonomy receipts, Broker protocol/native contracts, Evidence lifecycle,
redaction, service mirrors, dependency floors, package metadata, CI cost guard,
demo, Monorepo benchmark, installer/Doctor, and all predecessor portable DEP
checks remained Green. Hosted native and installed-wheel checks remain required
before independent signing.
