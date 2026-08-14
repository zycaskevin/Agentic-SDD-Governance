# Work Package: SDG v1.2 Hard Gates

## References

- Issue: #4
- SDD: `docs/AUTONOMOUS_DEVELOPMENT_V1_2.md`
- Evidence: `DEP-SDG-V12-HARD-GATES-001`
- Risk: L1

## Objective Contract

- Outcome: turn the three remaining v1.2 trust assumptions into fail-closed Runtime and CI gates.
- Success metric: unknown/dangerous actions cannot downgrade authority; L3 receipts are trusted and single-use; Merge policy is executed by CLI and CI.
- Guardrails: preserve autonomous routine L0/L1 work and all existing Production, Secret, permission, data, redaction, rollback, and integrity boundaries.
- Keep condition: all existing tests plus new adversarial tests pass without adding a human gate to routine engineering.
- Rollback condition: revert this bounded Work Package if a gate can authorize an unsafe action or blocks canonical reversible L0/L1 work.

## Scope

- In scope: action classification, signed approval receipt import, atomic L3 consumption, merge verifier, workflow integration, independent Reviewer bootstrap/signing CLI, schemas, docs, adapters, packaged resources, and tests.
- Non-scope: generating or handling an owner/Reviewer private key in the Builder session, executing Production operations, changing Billing, deploying, or configuring organization branch protection.
- Dependencies: approved v1.2 contract merged in PR #2; Python `cryptography` for Ed25519 verification.
- Evidence requirement: full DEP, adversarial tests, complete local suite, `validate`, `doctor`, `ci verify`, and Local Green Gate.
- Verification plan: reproduce each confirmed bypass before implementation; then require the same scenarios to fail closed and all routine paths to stay Green.

## Claim

- Agent: Codex
- Claimed at: 2026-08-13
- Expires at: completion of this bounded implementation pass
