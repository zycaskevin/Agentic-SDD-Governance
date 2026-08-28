# Work Package: Team-standard plain-language L2 decisions

Status: integrated, locally verified, and submitted in PR #57; not merged,
configured, or released

## References

- Issue: `issues/SDG-PRODUCT-RESET-001.md`
- Decision: `work-packages/DEC-SDG-EFFECT-BOUNDARY-001.md`
- Contract: `specs/sdg-product-contract.json`
- Risk: L1 implementation of an approved L2 product direction

## Objective Contract

- Outcome: team-standard records and reuses one explicit plain-language product
  choice without Owner-managed Terminal, SHA, signer, Broker, or cryptographic
  receipt. SHA-256 remains machine-generated and machine-verified integrity data.
- Success metric: exact-scope reuse continues automatically; scope change reopens
  one decision; regulated retains the signed receipt path; no digest becomes
  Owner UI or a copy/paste task.
- Guardrails: the record never grants L3 authority, never carries operation
  payloads, and cannot suppress sensitive-effect classification.
- Keep condition: L3 payload binding, trusted runtime context, one-use Broker
  consumption, and regulated signed approval code remain intact.
- Rollback condition: revert this slice if a plain L2 record can authorize an L3
  effect, survive a scope mismatch, or activate outside team-standard.

## Scope

- In scope: team-standard Profile, Policy Kernel, autonomy policy/schema,
  decision record/reuse/verify runtime, CLI wording, packaged resource mirrors,
  and targeted regression tests.
- Non-scope: regulated behavior changes, L3 execution, Broker service changes,
  Merge policy migration, installer reactivation, or release publication.
- Dependencies: `work-packages/WP-SDG-PRODUCT-RESET-001.md` within the
  single integrated product candidate.
- Evidence requirement: targeted autonomy, policy-schema, packaged-resource, and
  product-contract tests.
- Verification plan: run targeted tests, then confirm legacy L3 and solo-fast/regulated L2
  tests remain Green.

## Verification result

- 137 targeted autonomy, Owner-client compatibility, governance, product-contract,
  source-contract, schema, and packaged-mirror tests passed; one sandbox-only Unix
  socket test skipped.
- Source repository validation, autonomy-policy schema validation, and seven
  canonical/package mirror comparisons passed.
- The plain record is bound to one repository-relative request file and its
  machine-verified SHA-256; changing the card or scope reopens the decision without
  asking the Owner to handle the digest.
- Existing signed L2 compatibility tests and L3 receipt/Broker tests remain Green.
