# Work Package: Version-independent naming and deactivation contract

Status: locally verified and submitted in PR #57; not merged, configured, or
released

## References

- Issue: `issues/SDG-PRODUCT-RESET-001.md`
- Product decision: `work-packages/DEC-SDG-EFFECT-BOUNDARY-001.md`
- Naming decision: `work-packages/DEC-SDG-VERSIONLESS-PRODUCT-NAMING-002.md`
- Contract: `specs/sdg-product-contract.json`
- Risk: L1 implementation of approved product directions

## Objective Contract

- Outcome: active product artifacts use version-independent names, while this
  repository truthfully verifies that its own SDG installation and governance
  workflow remain deactivated.
- Success metric: no active product-reset path, identifier, test, branch, or
  worktree name contains `v2`; full repository tests no longer require removed
  self-governance files or treat retired R22 authority as current.
- Guardrails: retain real package/schema versions and historical migration-format
  references; preserve Installer capability for other repositories; do not
  reinstall Broker, bootstrap, `.agentic-sdd-governance`, `.agents`, or the
  repository governance workflow.
- Keep condition: regulated/L3 authorization continues to fail closed, canonical
  source assets remain byte-identical to packaged Installer resources, and
  temporary-project Installer tests remain Green.
- Rollback condition: revert if the rename changes a public wire format, if the
  Repo silently self-installs SDG, or if external-project setup/doctor/uninstall
  behavior regresses.

## Root Cause and Scope

- Root cause: the self-governance install and hosted governance workflow were
  intentionally removed from `main`, but repository-contract tests continued to
  require them. The superseded R22 test also treated its exact historical
  Owner-client digest as current after `autonomy.py` changed.
- In scope: active naming, internal links and identifiers, repository-contract
  expectations, deactivation proof, and external Installer regression tests.
- Non-scope: publishing, deployment, enabling hosted CI, deleting retained RC1
  security work, or weakening genuine L3 controls.

## Result

- Active product files, identifiers, links, tests, branch, and worktree now use
  version-independent semantic names. Real package/schema versions and historical
  rollback-format migration identifiers remain unchanged.
- Repository Contract now treats absent `.agentic-sdd-governance`, `.agents`, and
  `.github/workflows/governance.yml` as the intended deactivated state.
- Retired R22 material is preserved as history but its stale Owner-client binding
  is explicitly fail-closed and superseded; it is not silently refreshed.
- External-project Installer and Repository Contract regressions pass within the
  complete Local Green result: 620 tests collected, 615 passed, and 5
  platform-specific skips.
- Source validation and whitespace checks passed. No Broker, bootstrap, hosted
  workflow, deployment, publication, push, or external state change occurred.
