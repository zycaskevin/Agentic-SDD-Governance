# Verification

## Green command and result

Both hash-locked requirement sets were installed together; `pip check` passed with setuptools 83.0.0 and wheel 0.48.0. Focused filesystem, Broker, Evidence, redaction, and release suites passed 205 tests with four expected platform skips. The complete suite and exact-interpreter Local Green each passed 445 tests with 14 expected sandbox/platform skips. Validate and CI verify passed. Real Linux AF_UNIX tests passed eight tests with one expected installed-wheel provenance skip.

Wheel/sdist build and Twine passed. The offline bundle held 10 dependency wheels and four public assets; full release inventory verification passed. Fresh installed-wheel smoke passed without source-checkout import, with 13 bundle files/12 payload files, Codex and Hermes Doctor at 71 managed files each, demo PASS, and installed Linux Broker PASS.

Actual rollback cleanly reverted atomic product commit `642f21db6e08a80aba0819aa0fd8f2c0e20eecf4`, produced the exact Base product tree outside audit paths, passed Base Validate and 229 Base tests with one expected sandbox skip, reconciled Codex setup and Doctor at 66 managed files, passed Base build/Twine, and passed a clean offline installed-wheel consumer with `pip check`.

## Before/after evidence

Red is the independent R20 no-sign verdict and confirmed CodeRabbit findings. Green must bind the exact R21 atomic commit and the complete acceptance matrix without reusing an R20 receipt.

## Remaining limitations

Hosted Ubuntu/macOS, CodeRabbit final review, exact trusted-Base DEP/Gate verification, and a fresh independent Ed25519 receipt remain required. No package publication, production action, root installation, or private-key operation ran.
