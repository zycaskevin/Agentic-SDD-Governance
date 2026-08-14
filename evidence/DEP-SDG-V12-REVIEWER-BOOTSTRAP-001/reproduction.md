# Reproduction

## Expected

An independently assigned Reviewer should use a clean separate checkout, bootstrap its own Repo-external Ed25519 identity, register only the public trust JSON directly with GitHub, and sign the exact approved Merge gate. No owner key or digest courier step should exist.

## Actual

The GB10 Hermes Pilot reported 83/83 existing tests Green and a positive security review, but it continued after noticing untracked files, produced no Receipt, configured no GitHub trust variable, and asked Arthur to provide a Reviewer ID and Ed25519 public key.

## Deterministic steps

1. Assign a fresh Hermes session as independent Reviewer for PR #5.
2. Observe that the Repository exposes verifier and receipt schemas but no `sddgov reviewer` command.
3. Run `PYTHONPATH=src python3 -m unittest tests.test_reviewer -v` before the fix.
4. Confirm import fails with `ModuleNotFoundError: No module named 'sddgov.reviewer'`.
5. Observe the Pilot routes missing machine capability back to the product owner.

## Environment and preconditions

PR #5 Draft head `03127d57b5ba77ae29634f006f4412c704069c70`; no Production, Secret, customer data, or owner key was accessed. The sanitized Pilot result is the only externally supplied Evidence.
