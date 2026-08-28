# Work Package: Installer activation truth and release-readiness defaults

Status: integrated, locally verified, and submitted in PR #57; not merged,
configured, or released

## References

- Issue: `issues/SDG-PRODUCT-RESET-001.md`
- Product decision: `work-packages/DEC-SDG-EFFECT-BOUNDARY-001.md`
- Contract: `specs/sdg-product-contract.json`
- Evidence: `evidence/DEP-SDG-INSTALLER-DEFAULTS-001`
- Risk: L1 implementation of the approved effect boundary

## Objective Contract

- Outcome: a normal installation truthfully reports that Broker and Owner signing
  are not installed, started, created, or configured; Local Green contains no
  retired Owner-authorization gate; default hosted CI is named and operated as
  release readiness rather than Broker activation.
- Success metric: setup/doctor return an exact activation contract, the installed
  Agent instructions prohibit treating copied strong-authorization resources as
  active, CI Local Green passes without R22, and the Ubuntu/macOS workflow remains
  machine-only release proof.
- Guardrails: preserve regulated and exact L3 code, schemas, templates, synthetic
  tests, and fail-closed behavior; do not start services, provision identities,
  weaken tests, publish, deploy, push, or enable a hosted workflow.
- Keep condition: temporary-project setup/doctor/uninstall, full repository tests,
  source/resource mirrors, CI verification, and Local Green remain Green.
- Rollback condition: revert if setup claims a capability is active when it is
  merely copied, if regulated/L3 tests weaken, or if release readiness starts
  requiring an Owner action.

## Root Cause and Scope

- Root cause: setup copied reference service/signing resources without a
  machine-readable inactive status, while the source Repo Local Green retained a
  cryptographic verification command for superseded R22 authority.
- In scope: Installer manifest/report contract, adapters, product contract,
  installation docs, CI cost contract, hosted workflow naming, tests, and DEP.
- Non-scope: splitting or executing the true publication workflow, system service
  installation, signer provisioning, root operations, or artifact publication.
