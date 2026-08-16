# Verification

## Green command and result

- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: PASS, 205/205.
- `PYTHONPATH=src python3 -m sddgov.cli validate .`: PASS.
- `PYTHONPATH=src python3 -m sddgov.cli ci verify .`: PASS; `post_merge_verification` is `manual_only` and no automatic `push` event remains.
- `PYTHONPATH=src python3 -m sddgov.cli doctor .`: PASS, 64 managed files.
- The historical PR #14 rollback drill: PASS after deterministic managed-governance reconciliation; Doctor and the declared `unittest` module return Green.
- Candidate static rollback for atomic implementation `a0082496255bab3765161b913ae7b67928107236`: PASS; the inverse is conflict-free and restores the exact Base outside Evidence/audit paths.
- Candidate runtime rollback post-condition at Evidence Head `42d4b2467c00287513267d6877bdeb3b8adab8d4`: PASS; reconciliation, Doctor, and the declared `unittest` module return Green.
- Wheel and sdist build: PASS.
- Fresh dependency-resolved wheel install and `pip check`: PASS; `cryptography 50.0.0` satisfies the patched dependency line.
- Fresh Codex and Hermes setup plus Doctor: PASS, 64 managed files each.
- Offline synthetic Muse pilot: PASS; `network_used=false` and `real_data_used=false`.

## Before/after evidence

Before: exact tree rollback passes while Doctor fails, and two automatic hosted events execute. After: rollback reconciliation makes Doctor and tests Green, and CI Cost Guard rejects automatic post-merge `push` while preserving the required PR route plus manual dispatch.

## Remaining limitations

GitHub `main` protection and required-check Ruleset activation is an external
Operational Action and remains outside this code mutation until explicitly
authorized. Independent Review, hosted verification, Merge, and Release remain
distinct later proofs.
