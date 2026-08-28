# Work Package: Product reset integration on AF27 mainline

Status: corrected product candidate under exact local verification; final
Evidence, hosted readiness, CodeRabbit, and independent review pending; not
merged, configured, or released

## References

- Base: `412c0416965e1091b61fa4ea7790498c36ca5505`
- Product decision: `work-packages/DEC-SDG-EFFECT-BOUNDARY-001.md`
- Product contract: `specs/sdg-product-contract.json`
- AF27 boundary: `docs/TRUSTED_RUNNER_V0_2_AF27.md`
- Release handoff: `work-packages/WP-SDG-RELEASE-HANDOFF-006.md`
- Risk: L1 integration of an already approved product boundary; no new Owner
  decision and no real external effect are in scope.

## Objective Contract

- Outcome: port the product reset onto the exact current mainline without
  reactivating repository self-governance or AF27 production authority.
- Success: normal development and release readiness require zero Owner
  operations; team-standard L2 records one plain-language choice; real release
  or production effects remain one exact native approval; AF27 production mode
  continues to fail closed.
- Guardrails: preserve AF27 containment tests and hard deny, keep installer
  activation claims truthful, do not ask the Owner to relay SHA values, review
  findings, receipts, Terminal commands, or signer material.
- Keep condition: targeted integration tests, full Local Green, CI contract,
  package/Twine/fresh-wheel checks, rollback drill, and portable strict Evidence
  all pass against exact refs.
- Rollback condition: revert the single integrated product commit if the product
  reset weakens AF27, activates governance by default, creates an external
  effect, or makes Owner relay work part of normal development.

## Scope

- In scope: product/effect contracts, conversational team-standard decisions,
  installer truthfulness, release-readiness handoff, deterministic tests,
  documentation, and exact-ref Evidence.
- Implementation non-scope: push, pull request, hosted run, external review,
  Merge, tag, GitHub Environment configuration, registry upload, broker
  installation, production activation, credential access, or public release.
  Delivery is tracked separately by public PR #57 without changing the approved
  product boundary.

## Resolved finding

Full Local Green revealed one environment-dependent test expectation: a machine
with a real fixed approver store returned the stricter fail-closed reason
`approval_authority_identity_changed`, while an unconfigured host returned
`approval_verification_failed`. The test now simulates the unavailable control
plane explicitly. Runtime authority checks were not weakened.

## Result

- Exact Base: `412c0416965e1091b61fa4ea7790498c36ca5505`.
- The corrected product tree will be one single-parent candidate commit. Its
  exact ref will be bound only by the later Evidence-only commit.
- Full Local Green collected 620 tests: 615 passed and 5 platform-specific
  skips; CI contract and source validation passed. Build/Twine, hash-locked offline bundle,
  fresh-wheel smoke, and isolated exact-tree rollback must still be rerun
  against the resulting exact corrected product ref before Evidence closes.
- AF27 production remains hard-denied. The live PR still points to an older
  revision; Ubuntu/macOS and CodeRabbit results for that revision do not count
  for the corrected product. Final hosted readiness, exact CodeRabbit review,
  independent review, Evidence, and Gate are pending. No Merge, tag, registry
  write, Broker installation, or release occurred.
