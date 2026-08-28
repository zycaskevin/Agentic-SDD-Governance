# Work Package: SDG product boundary baseline

Status: integrated, locally verified, and submitted in PR #57; not merged,
configured, or released

## References

- Issue: `issues/SDG-PRODUCT-RESET-001.md`
- Decision: `work-packages/DEC-SDG-EFFECT-BOUNDARY-001.md`
- Product charter: `docs/SDG_PRODUCT_CHARTER.md`
- Risk: L1 implementation of an Owner-selected L2 product direction

## Objective Contract

- Outcome: establish one executable product boundary before changing the runtime.
- Success metric: the JSON contract validates against its schema and semantic tests
  prevent Owner operations from re-entering development or release readiness.
- Guardrails: retain fail-closed L3 controls for real external effects; do not
  publish, deploy, provision, install, start, sign, merge, or delete legacy work.
- Keep condition: machine integrity, independent review, CI, rollback, redaction,
  and artifact verification remain Agent/machine responsibilities.
- Rollback condition: revert this bounded documentation/contract/test slice if it
  cannot distinguish readiness evidence from actual external execution.

## Scope

- In scope: product charter, decision record, machine-readable contract, schema,
  semantic contract tests, and roadmap/readme status.
- Non-scope: runtime classifier migration, CLI behavior, installer behavior,
  Broker provisioning, signing, RC1 publication, or consumer-repo reactivation.
- Dependencies: integration Base
  `412c0416965e1091b61fa4ea7790498c36ca5505` and
  `work-packages/WP-SDG-AF27-PRODUCT-RESET-INTEGRATION-007.md`.
- Evidence requirement: targeted contract tests and repository diff checks.
- Verification plan: validate the schema, run semantic tests, and inspect the
  final diff for accidental activation of legacy approval machinery.

## Verification result

- The integrated product contract has 10 passing semantic tests.
- Full Local Green collected 620 tests: 615 passed and 5 platform-specific
  skips; JSON/schema,
  repository validation, and diff whitespace checks passed.
- Repository self-governance remains deactivated and AF27 production authority
  remains hard-denied. Exact refs and package proof are recorded by the
  integration Work Package and its Evidence.
