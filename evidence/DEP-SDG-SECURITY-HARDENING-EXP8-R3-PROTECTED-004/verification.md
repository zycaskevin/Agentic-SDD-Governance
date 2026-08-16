# Verification

## Green command and result

Targeted Merge Gate and repository-contract tests pass, as does the full 187-test suite with one sandbox-only AF_UNIX skip; the real AF_UNIX positive path then passed on this candidate outside the socket-restricted sandbox. `sddgov validate`, CI verify, and this DEP's strict full/portable verification pass. The rebuilt wheel installed cleanly at `/private/tmp/sdg-exp8-r3-final-wheel-PYjrEj`; `pip check`, Codex/Hermes setup and doctor (63 managed files each), and the offline synthetic Muse pilot pass. Wheel SHA-256: `07eff7e1ba85f5fb37f38edae6914ef5ea62ccd64487e8e3b4183f56f1df82e8`. Sdist SHA-256: `cea37af93af4d39d49b793a0a6fca4463d386f4481069c186ac52c5e0453b406`.

## Before/after evidence

Before: three Agent-loaded governance surfaces were not protected. After: all representative paths match trusted Base patterns and therefore enter the existing signed independent-review requirement.

## Remaining limitations

Local pattern coverage does not provide an independent receipt. The next exact candidate still requires fresh P0=0/P1=0 review before merge or release.
