# Verification

## Green command and result

At exact product commit `a5589c5f2d1904a13a1d9da4677aa6354cb3ef39`, `PYTHONPATH=src python -m pytest -q` passed 617 tests with 5 platform-specific skips. Source validation and CI verification passed.

## Before/after evidence

The machine product contract now rejects provider status as review evidence and limits automatic retry to one per exact revision. Signed independent review, full Merge Gate, rollback, Evidence, and hosted CI remain required.

## Remaining limitations

Fresh Gate, independent receipt, hosted CI, merge, GitHub Environment/Trusted Publishing, tag, registry, GitHub Release, and publication remain pending.
