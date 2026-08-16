# Fix Scope

## Smallest sufficient change

Add a closed rollback post-condition contract and local drill, enforce a manual-only post-merge CI policy, remove the automatic `push: main` trigger, and align the already-approved review-sharing wording/tests.

## Files or components in scope

- `src/sddgov/merge_gate.py` and rollback regressions.
- `src/sddgov/ci_guard.py`, CI Cost Guard Schema/template/copies, workflow, and regressions.
- PR #14 rollback/reproduction records and the new DEP.
- Policy/Skill/docs/tests and their packaged/installed copies for the eight confirmed P2 consistency gaps.

## Explicit non-scope

GitHub Ruleset mutation, Billing, runners, credentials, public Release, Production deployment, and any weakening of required tests, signed Review, Evidence, or L2/L3 safety.

## Blast radius

Local Merge verification becomes stricter and performs a disposable rollback drill for the new contract. Automatic Governance runs are limited to non-Draft PRs; Release verification remains explicitly dispatchable. Review-sharing authority is clarified but not expanded.
