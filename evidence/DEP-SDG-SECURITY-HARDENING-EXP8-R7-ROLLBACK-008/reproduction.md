# Reproduction

## Expected

The Gate-selected full SHA must be inside the candidate range and its inverse must apply without a conflict at the exact reviewed Head.

## Actual

The selected `d7e16f2e5695f6fba28c262daf8e6819dd0c0c35` passed format and ancestry checks, but both an independent disposable `git revert --no-edit` drill and a tree-level simulation returned conflicts.

## Deterministic steps

1. Checkout exact reviewed Head `77a68dc32e1e14022829cff4a0fcf966ed9be3c4` in a disposable clone.
2. Read the selected ref from `evidence/DEP-SDG-SECURITY-HARDENING-EXP8-001/rollback.md`.
3. Run a no-commit revert or the equivalent three-way Git tree simulation.
4. Observe conflicts in the DEP1 and R6 Evidence files changed after the selected commit.

## Environment and preconditions

Exact Base `f44cb5f4897f6c821f817fcf178581b43777163a`; no Production data, credentials, or network access. Raw command evidence remains under local `private/raw`; only the redacted derivative is shareable.
