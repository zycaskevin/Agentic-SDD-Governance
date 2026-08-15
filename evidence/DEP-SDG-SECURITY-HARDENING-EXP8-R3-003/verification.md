# Verification

## Green command and result

The full 187-test suite passes with one sandbox-only AF_UNIX skip; the real AF_UNIX positive path then passed on this candidate outside the socket-restricted sandbox. `sddgov validate`, CI verify, and this DEP's strict full/portable verification pass. The final wheel installed cleanly at `/private/tmp/sdg-exp8-r3-final-wheel-PYjrEj`; `pip check`, Codex/Hermes setup and doctor (63 managed files each), and offline synthetic Muse pilot all pass. Wheel SHA-256: `07eff7e1ba85f5fb37f38edae6914ef5ea62ccd64487e8e3b4183f56f1df82e8`. Sdist SHA-256: `cea37af93af4d39d49b793a0a6fca4463d386f4481069c186ac52c5e0453b406`.

## Before/after evidence

Before: candidate `d03213a` reused an exact L2 decision despite foreign L3 fields. After: each foreign field returns `BLOCKED request_contains_fields_outside_closed_category_schema` before decision lookup.

## Remaining limitations

Local Green is not independent approval. A new exact candidate requires a fresh Reviewer result with P0=0/P1=0 before any receipt, merge, or release step.
