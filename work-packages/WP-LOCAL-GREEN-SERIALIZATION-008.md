# Work Package: Local Green Cross-Checkout Serialization

Status: locally verified; ready for independent review; not installed

## References

- Issue: `issues/SDG-CI-LOCK-001.md`
- SDD: `docs/CI_COST_GUARD.md`
- Risk: L1 reliability regression

## Objective Contract

- Outcome: independent current-user Local Green invocations cannot execute
  repository-controlled critical sections concurrently.
- Success metric: deterministic cross-process contention and orchestration-order
  regressions pass; existing CI Guard contract/command behavior stays Green.
- Guardrails: no retries, test suppression, authority change, repository-data
  lock material, HOME override, hosted workflow change, or destructive action.
- Keep condition: focused and full unit suites, source validation, Ruff, diff
  check, strict DEP verification, and repository Local Green pass.
- Rollback condition: lock acquisition is bypassable, leaves unsafe records,
  changes command results, or breaks a supported platform without an explicit
  fail-closed disposition.

## Scope

- `src/sddgov/ci_guard.py`
- CI Guard tests and documentation
- L1 DEP and engineering records

## Authority

The owner directed continued development on 2026-08-23 Asia/Taipei
(2026-08-22 UTC) after a machine-
verifiable VAM-006A gate reliability failure. The team-standard profile
authorizes reversible L1 implementation, tests, evidence, and local commits.
The owner separately authorized this feature-branch Push on 2026-08-23
Asia/Taipei (2026-08-22 UTC). That
directive does not authorize PR creation, release, shared installation, merge,
or live action.

## Verification result

The atomic implementation revision is the direct parent of the DEP Proof
commit and is bound there by exact SHA. It passed focused concurrency
contracts, targeted changed-file Ruff safety rules (`E4,E7,E9,F`), managed-copy
parity, source validation, diff checks, and the exact repository Local Green
Gate (`237` total: `236` passed and one platform-dependent skip). The descendant
commit is bounded to DEP Proof records.
