# Verification

## Green command and result

`PYTHONPATH=src python -m unittest discover -s tests -v` passed 357 tests with two explicit skips in the fresh two-lock workflow environment. Doctor, `validate`, `ci verify`, and `ci local-gate` passed. Package construction validates source first, then builds and Twine-checks RC1 distributions, assembles the locked offline bundle, and completes fresh-wheel Codex/Hermes smoke tests without importing the checkout.

## Before/after evidence

Red: `terminal--r13-independent-review-red.txt` records receipt refusal for the trusted-Base topology failure and isolated environment failure; `terminal--r13-release-venv-red.txt` preserves the failing workflow-contract assertion. Green: the Local Green, CI verify, Local Gate, package proof, release bundle JSON, and fresh-wheel JSON artifacts bind the corrected behavior.

The package proof produced wheel SHA-256 `89bd8f199e76e780cfaca97bf929a2c9b4aef0592f8a473b27b28920f33f1ae1`, sdist SHA-256 `98cfb2ed49b34a8effb12ec5039f41941eb68c9ae8728ea88735d09a61f185a7`, and offline archive SHA-256 `46880c7672583edfa31672b1a751ca05fdb96b800dfaa314682d7122557b0a3c`. The bundle contains ten dependency wheels; fresh-wheel verification manages 72 files for Codex and Hermes and uses synthetic data only.

Rollback and exact-Base Merge verification are intentionally recorded after this Green Evidence snapshot so the immutable audit Head can be exercised. They must pass before Proof and before any independent receipt is requested.

## Remaining limitations

Public TestPyPI/PyPI/GitHub Release, protected GitHub environments, real Owner key custody, root Broker installation, WSL2/macOS privileged rehearsal, and the independent Ed25519 protected-file receipt remain external. The Gate stays BLOCKED until the new reviewer independently approves the rebuilt exact Head. PR #34 remains unchanged as a failed-review audit record, and no benchmark superiority claim is made.
