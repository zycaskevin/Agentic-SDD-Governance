# Verification

## Green command and result

Python 3.12 with both hash-locked requirements passed `pip check`, 381 unit
tests, Validate, CI verify, and Local Gate. Real Linux source tests passed the semantic suite;
a fresh installed-wheel consumer passed all eight native tests with checkout
imports rejected. Build/Twine, offline bundle, and fresh-wheel smoke passed;
Codex/Hermes Doctor each validated 71 files and Broker health/cleanup was Green.

## Before/after evidence

Red binds hosted PR #37 run `32549653876`: Linux Green, macOS-15 pre-publication
path-length failure. Green binds the short-root/Darwin-boundary assertions,
installed-wheel import check, exact atomic topology, and exact Base rollback.

## Remaining limitations

The final hosted macOS installed-wheel result, trusted-Base merge verification,
and fresh independent Ed25519 receipt remain external. Public release/PyPI,
root Broker installation, WSL2 rehearsal, production state, and key custody are
not performed. Merge remains blocked until every applicable external gate passes.
