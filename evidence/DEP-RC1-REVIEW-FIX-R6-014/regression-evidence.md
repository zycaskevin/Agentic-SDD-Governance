# Regression Evidence

## Regression test added or strengthened

Focused cases cover release lock/metadata binding, private bundle snapshotting,
consumer validation, independent Broker deadlines/backend normalization,
generation-safe redaction cleanup, harmless dash separators, immutable Evidence
inventory, CI job maps, portable README commands, service hardening, incomplete
pilot results, and deterministic benchmark claims.

## Related tests executed

The recorded Red command ran 91 tests and failed on R5. The first full Local
Green ran 289 tests with two sandbox-specific skips and passed repository
validation; the final suite added the immutable-inventory regression and passed
290 tests with the same two explicit skips. Package build and Twine inspection passed; an aarch64 offline bundle
bound ten locked dependency wheels, and fresh-wheel smoke passed Codex/Hermes
setup, Doctor, validation, and the offline quick demo.

## Unaffected paths sampled

The focused and full suites also sample symlink/hardlink rejection, exact bundle
inventory, provider-credential redaction, Evidence transaction races, installer
upgrades, trusted-base rollback, OIDC workflow permissions, autonomy receipts,
reviewer identity separation, and all existing portable Proof DEPs.
