# Work Package: Effect-based Merge and reality boundary

Status: integrated, locally verified, and submitted in PR #57; not merged,
configured, or released

## References

- Issue: `issues/SDG-PRODUCT-RESET-001.md`
- Decision: `work-packages/DEC-SDG-EFFECT-BOUNDARY-001.md`
- Contract: `specs/sdg-product-contract.json`
- Risk: L1 implementation of an approved L2 product direction

## Objective Contract

- Outcome: effect-free Merge and Release Readiness run as L1 with zero Owner
  operations, while actual Production deploy and public publication use one exact
  L3 operation after readiness passes.
- Success metric: the classifier returns autonomous channel metadata for
  effect-free requests, rejects workflow-step requests that hide real effects,
  and accepts `public_release` only with `public_publish: true` at L3.
- Guardrails: no L1/L2 baseline decision authorizes Production execution; L3
  operation payload, runtime context, signature, and one-use Broker remain intact.
- Keep condition: CI, evidence, rollback, artifact verification, and independent
  review remain readiness requirements but never Owner message-relay tasks.
- Rollback condition: revert this slice if an effect-bearing Merge can continue as
  L1/L2 or if effect-free readiness starts prompting the Owner.

## Scope

- In scope: effect categories, classifier results, Production-deploy boundary,
  policy/schema, operation receipt schema, packaged mirrors, docs, and tests.
- Non-scope: executing a real deploy/release, provisioning Broker or credentials,
  changing hosted workflow configuration, or publishing a package.
- Dependencies: `work-packages/WP-SDG-TEAM-STANDARD-L2-002.md` within the
  single integrated product candidate.
- Evidence requirement: autonomy, deployment, schema, packaged-resource, and
  product-contract tests.
- Verification plan: prove effect-free L1 autonomy, downgrade rejection, exact
  public-release L3 prompting, and preserved L3 consumption tests.

## Result

- Effect-free `merge` and `release_readiness` are exact L1 channels with zero
  Owner operations. A request with real effects is blocked for machine
  reclassification into its canonical L3 operation; it does not prompt the Owner
  under a misleading workflow-step name.
- Actual Production deploy requires green readiness guards and one exact L3
  operation. An L1 baseline or L2 product decision cannot authorize execution.
- Public publication is the canonical `public_release` L3 category and must bind
  the `public_publish` effect.
- Full Local Green collected 620 tests: 615 passed and 5 platform-specific
  skips. Source
  validation passed, canonical and packaged governance resources remain
  byte-identical, repository self-governance remains absent, and superseded R22
  authority remains fail-closed rather than silently refreshed.
