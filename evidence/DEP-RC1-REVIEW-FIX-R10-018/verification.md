# Verification

## Green command and result

`.venv/bin/python -m sddgov.cli ci local-gate .` passed with 333 tests, two explicit skips, and successful repository validation. Source validation ran before package construction. RC1 wheel/sdist, Twine, locked 11-wheel offline bundle, fresh-wheel Codex/Hermes smoke, and the actual Rollback v3 drill all returned PASS.

## Before/after evidence

Red: the focused pre-fix run produced six failures and three errors, then two fail-closed rollback/media compatibility reproductions exposed an unsafe historical metadata rewrite. Green: `terminal--r10-local-green.txt`, `terminal--r10-package-proof.txt`, the two JSON release reports, and `terminal--r10-rollback-drill.txt` bind the corrected behavior. Artifact SHA-256 values and exact commit topology are in `git--r10-git-context.txt`.

The R10 bootstrap DEP deliberately retains manifest schema 1.0 and legacy JSON labels so the trusted Base remains able to verify it after rollback. Product regression tests prove that packages created after the implementation is trusted Base use schema 1.1 and `application/json`; current strict verification accepts the legacy bridge only for schema 1.0.

## Remaining limitations

Public TestPyPI/PyPI/GitHub Release, protected GitHub environments, real Owner key custody, root Broker installation, WSL2/macOS privileged rehearsal, and the independent Ed25519 protected-file review remain external and were not simulated. The Merge Gate must remain BLOCKED until the independent signed receipt and exact final Head binding exist. No claim of benchmark superiority is made.
