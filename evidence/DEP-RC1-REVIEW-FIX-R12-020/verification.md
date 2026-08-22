# Verification

## Green command and result

`PYTHONPATH=src python -m unittest discover -s tests -v` passed 357 tests with two explicit skips. Source validation ran before package construction. The RC1 wheel/sdist, Twine, locked ten-wheel offline bundle, fresh-wheel Codex/Hermes smoke, and actual Rollback v3 drill all returned PASS.

## Before/after evidence

Red: the focused pre-fix run produced 12 failures and four errors across 13 tests at the reviewed boundaries. Green: `terminal--r12-local-green.txt`, `terminal--r12-package-proof.txt`, the two JSON release reports, and `terminal--r12-rollback-drill.txt` bind corrected behavior. Exact review identities, commit topology, and dispositions are in `git--r12-git-context.txt` and `git--r12-review-bindings.txt`.

The Red and rollback transcripts were collected from deterministic pre-redacted fixed-point copies because current and trusted-Base redactors intentionally differ at local-path chunk boundaries. The original transcript SHA-256 values are `db640ec52de21f979f05e00b6e3b55c7752f8aabb72f40995b6a1c0a2f562dd7` and `29e9be9f324ded3909136f83d163e23be1bc7618da779aa3617b81de9b802f37`, respectively. The normalized copies preserve the same test verdicts, contain no unredacted workspace paths, and can be independently reproduced by both verifier generations.

The package proof produced wheel SHA-256 `61d2a752346ca90d43e66b6fbbfef5f199143c7ff68a7063e0233621a085702e`, sdist SHA-256 `8f8e0a3557b46e0acfc94b79b4f94c4bb43014dab5055b43a8a463bd4c42e234`, and offline archive SHA-256 `039f16fdf4f71c057c0b54b6a694f239c8cb09351e59cccda88e8866575b2500`. The fresh-wheel process did not import the source checkout, verified all bundle hashes, managed 72 files for both Codex and Hermes, and used only synthetic data.

The R12 rollback transcript first verifies the external release environment with `pip check` and imports build/Twine, then reverts the exact atomic implementation at an audit-only descendant. It proves byte-equivalent trusted Base outside audit paths, passes Base Doctor/Validate/229 tests, rebuilds and checks Base artifacts, and installs the expected `0.2.0-experimental.8` wheel.

This bootstrap DEP deliberately retains manifest schema 1.0 and legacy text labels for JSON-suffixed collector artifacts so the trusted Base verifier can consume every retained audit descendant. Product tests prove that packages created after the implementation use schema 1.1 and `application/json`; current strict verification accepts the legacy bridge only for schema 1.0.

## Remaining limitations

Public TestPyPI/PyPI/GitHub Release, protected GitHub environments, real Owner key custody, root Broker installation, WSL2/macOS privileged rehearsal, target-specific `SystemCallFilter` validation, and the independent Ed25519 protected-file review remain external and were not simulated. Native Windows support remains limited to guarded installation guidance and synthetic evaluation; full descriptor-bound Evidence/release/Merge/rollback/Broker workflows require Linux, macOS, or WSL2. The Merge Gate must remain BLOCKED until the independent signed receipt and exact final Head binding exist. No PR #33 review thread was replied to or resolved, and no benchmark superiority claim is made.
