# Verification

## Green command and result

Local Green and Local Gate each record 366 passing tests with two sandbox-only
skips; CI verification passed. Package proof binds both hash-locked sets,
setuptools 83.0.0, wheel 0.48.0, build/Twine, and hashes. Fresh-wheel smoke
passes bundle verification, Codex/Hermes Doctor, isolation, and the demo.

## Before/after evidence

Red binds PR #35's unsafe pin, pathname conflict, and missing asset contract.
Green binds hostile Broker/logging and parity tests. The rollback transcript
proves exact Base before reconciliation, 229 Base tests, Doctor/Validate,
build/Twine, and a clean Base-wheel consumer. Reconciliation changes only the
expected manifest `installed_at` field.

## Remaining limitations

Public registries/releases, protected environments, real key custody, root
Broker installation, WSL2/macOS privileged rehearsal, and independent Ed25519
review remain external. Merge remains BLOCKED until a fresh receipt binds the
final R14 Head. No benchmark superiority is claimed.
