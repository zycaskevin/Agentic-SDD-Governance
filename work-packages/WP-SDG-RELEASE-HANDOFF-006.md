# Work Package: Exact release handoff and one native approval

Status: corrected product candidate under exact local verification; final
Evidence and hosted readiness pending; not merged, configured, or released

## References

- Issue: `issues/SDG-PRODUCT-RESET-001.md`
- Product decision: `work-packages/DEC-SDG-EFFECT-BOUNDARY-001.md`
- Contract: `specs/sdg-product-contract.json`
- Operational guide: `docs/RELEASE_HANDOFF.md`
- Risk: L1 implementation of the approved release/production effect boundary;
  executing publication remains L3

## Objective Contract

- Outcome: release readiness produces one immutable, machine-verifiable artifact;
  publication consumes only the exact successful readiness run and waits at one
  native protected Environment after every machine check passes.
- Success metric: the Owner handles no SHA, run ID, artifact digest, Terminal,
  signer, receipt, or review finding; the publication workflow has one protected
  job and no source build; the readiness workflow has no write/OIDC permission or
  external publication step.
- Guardrails: retain exact tag/default-branch ancestry, complete asset inventory,
  cross-workflow run binding, pinned Actions, registry round-trip equality, and
  fail-closed Environment checks. Do not configure GitHub, create a tag, dispatch
  a workflow, push, or publish in this Work Package.
- Keep condition: targeted contracts, full Local Green, source validation, CI Cost
  Guard, and portable strict Evidence pass.
- Rollback condition: revert if readiness can cause a real external effect, if
  publication accepts a caller-selected or mismatched artifact, if more than one
  Owner approval is required, or if the Owner must relay integrity data.

## Scope

- In scope: tag-only candidate artifact production, `workflow_run` handoff verification,
  one protected publication job, product/schema contracts, tests, release guide,
  and Evidence.
- Non-scope: external Environment or Trusted Publisher configuration, secrets,
  tags, tag-triggered `release-candidate`/`publish` hosted runs, registry writes,
  GitHub Releases, Merge, and public release.

## Result

- Full Local Green collected 620 tests: 615 passed and 5 platform-specific
  skips. Twine
  inspection, the hash-locked offline bundle, fresh-wheel smoke, and hosted
  Ubuntu/macOS readiness must still be rerun against the exact corrected
  product ref before Evidence closes.
- No final integration Evidence exists in the product commit itself. A later
  Evidence-only commit will bind the exact product ref and verified results.
- No tag, `release-candidate`/`publish` workflow, protected Environment,
  registry, GitHub Release, or publication action was created or invoked.
