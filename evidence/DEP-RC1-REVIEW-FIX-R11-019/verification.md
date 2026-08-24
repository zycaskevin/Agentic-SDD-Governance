# Verification

## Green command and result

`.venv/bin/python -m sddgov.cli ci local-gate .` passed with 346 tests, two explicit skips, and successful repository validation. Source validation ran before package construction. RC1 wheel/sdist, Twine, locked 11-wheel offline bundle, fresh-wheel Codex/Hermes smoke, and the actual Rollback v3 drill all returned PASS.

## Before/after evidence

Red: the focused pre-fix run produced six failures and nine errors across the reviewed boundaries. Green: `terminal--r11-local-green.txt`, `terminal--r11-package-proof.txt`, the two JSON release reports, and `terminal--r11-rollback-drill.txt` bind the corrected behavior. Artifact SHA-256 values, exact review identities, and commit topology are in `git--r11-git-context.txt` and `git--r11-review-bindings.txt`.

The Red, Local Green, and rollback transcripts were collected from deterministic pre-redacted fixed-point copies because current and trusted-Base redactors intentionally differ at local-path chunk boundaries. Their original transcript SHA-256 values remain bound in `git--r11-git-context.txt`; the normalized copies contain the same test verdicts and no unredacted workspace paths. Both verifier generations independently reproduce the final shareable bytes.

The R11 bootstrap DEP deliberately retains manifest schema 1.0 and legacy JSON labels so the trusted Base remains able to verify it after rollback. Product regression tests prove that packages created after the implementation is trusted Base use schema 1.1 and `application/json`; current strict verification accepts the legacy bridge only for schema 1.0. The package proof demonstrates one locked `--no-isolation` build and does not claim byte-for-byte reproducibility across time or hosts.

## Remaining limitations

Public TestPyPI/PyPI/GitHub Release, protected GitHub environments, real Owner key custody, root Broker installation, WSL2/macOS privileged rehearsal, and the independent Ed25519 protected-file review remain external and were not simulated. Native Windows support remains limited to documentation and synthetic evaluation; full descriptor-bound Evidence/release/Merge/rollback/Broker workflows require Linux, macOS, or WSL2. The Merge Gate must remain BLOCKED until the independent signed receipt and exact final Head binding exist. No claim of benchmark superiority is made.
