# Reproduction

## Expected

The release lock must exclude reviewed vulnerable build-tool ranges. The Broker
must remove its own socket after every post-bind setup failure while preserving
any replacement pathname. macOS logging must have one owner that can rotate or
retain output without a missing reopen protocol. Canonical, installed, and
embedded governance assets must agree.

## Actual

The PR #35 candidate locked `setuptools==80.10.2`, below the reviewed safe
floor. A forced first pathname `lstat` failure after `bind()` left the created
socket behind. The launchd plist held pathname log descriptors while a
newsyslog rule rotated those paths without signalling or reopening the Broker.
That asset was also omitted from the managed-required validation set.

## Deterministic steps

1. Inspect the exact PR #35 release lock against the reviewed advisory floors.
2. Force the first pathname identity lookup after a real socket bind to fail.
3. Replace the pathname before cleanup and assert the replacement survives.
4. Inspect launchd, newsyslog, packaged resources, installer, and validation.
5. Run the R14 hostile tests, full suite, package smoke, and rollback drill.

## Environment and preconditions

Red used PR #35 Head `3d30519fdd96fb5500be573a1345633180d8b305`
against Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. Green uses
single-parent product commit `9e8bd708fbfea7a995d6256a4b2e5f9e04d2c9d7`
on that Base, Python 3.12, and both hash-locked dependency sets. Exercises were
disposable and used no production data, Owner key, reviewer key, or root store.
