# Verification

## Green command and result

`PYTHONPATH=src python -m unittest discover -s tests -v` passed 357 tests with two explicit skips in the fresh two-lock workflow environment. Doctor, `validate`, `ci verify`, and `ci local-gate` passed. Package construction validates source first, then builds and Twine-checks RC1 distributions, assembles the locked offline bundle, and completes fresh-wheel Codex/Hermes smoke tests without importing the checkout. Rollback v3 passed exact topology, exact non-audit Base equality, 229 Base tests with two explicit skips, Base packaging, and fresh install.

## Before/after evidence

Red: `terminal--r13-independent-review-red.txt` records receipt refusal for the trusted-Base topology failure and isolated environment failure; `terminal--r13-release-venv-red.txt` preserves the failing workflow-contract assertion. Green/Proof: the Local Green, CI verify, Local Gate, package proof, release bundle JSON, fresh-wheel JSON, and rollback drill artifacts bind the corrected behavior.

The package proof produced wheel SHA-256 `89bd8f199e76e780cfaca97bf929a2c9b4aef0592f8a473b27b28920f33f1ae1`, sdist SHA-256 `98cfb2ed49b34a8effb12ec5039f41941eb68c9ae8728ea88735d09a61f185a7`, and offline archive SHA-256 `46880c7672583edfa31672b1a751ca05fdb96b800dfaa314682d7122557b0a3c`. The bundle contains ten dependency wheels; fresh-wheel verification manages 72 files for Codex and Hermes and uses synthetic data only.

`terminal--r13-rollback-drill.txt` proves the atomic parent equals Base and each descendant through the exercised Head changes only `evidence/**`. Reverting the atomic commit yields exact Base outside Evidence, passes Base Doctor/Validate/229 tests, builds and checks Base distributions, and installs the expected `0.2.0-experimental.8` wheel.

The original rollback terminal capture has SHA-256 `eef73a4524b382f996061060ec1f11d7de1ae9ba26bb5cd8dd3c0b73d975507c`. Its tracked artifact is the deterministic pre-redacted, LF-normalized fixed-point copy with SHA-256 `58d5873b1e2eb6122a85d3db8fe0ddd31a8a044d930c33aaff8312a150f2e9b9`; verdicts and command output are preserved while local paths and CRLF capture framing are removed. Both current and trusted-Base redactors reproduce this copy byte-for-byte.

This bootstrap DEP retains manifest schema 1.0 and legacy text labels for JSON-suffixed collector artifacts so the exact trusted Base verifier can consume every audit descendant. Current product tests separately prove new schema 1.1 packages use `application/json`.

## Remaining limitations

Public TestPyPI/PyPI/GitHub Release, protected GitHub environments, real Owner key custody, root Broker installation, WSL2/macOS privileged rehearsal, and the independent Ed25519 protected-file receipt remain external. The Gate stays BLOCKED until the new reviewer independently approves the rebuilt exact Head. PR #34 remains unchanged as a failed-review audit record, and no benchmark superiority claim is made.
