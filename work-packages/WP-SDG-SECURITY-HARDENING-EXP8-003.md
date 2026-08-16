# Work Package: SDG experimental.8 Security Hardening

## References

- Issue: #11
- Baseline: `v0.2.0-experimental.7` / `f44cb5f4897f6c821f817fcf178581b43777163a`
- SDD: `docs/HARD_GATES_V1_2.md`
- Evidence: `DEP-SDG-SECURITY-HARDENING-EXP8-001`
- Risk: L1 security regression repair

## Objective Contract

- Outcome: close the confirmed classification, workflow-semantics, proof-freshness, filesystem, rollback, dependency, and interruption-state gaps in experimental.7.
- Success metric: every confirmed defensive probe is a permanent regression test; the complete suite, strict DEP, package smoke, and offline synthetic Muse pilot pass; fresh independent review reports P0=0 and P1=0.
- Guardrails: preserve L0/L1 autonomy and existing L2/L3 authority; do not use Production, credentials, real Muse data, Billing, or stable-release publication.
- Keep condition: fail closed for ambiguous authority and unverifiable evidence without turning ordinary clean files or reversible engineering into human approval gates.
- Rollback condition: revert this Work Package if the fix weakens authority boundaries, destroys later-writer data, or makes routine L0/L1 work require owner approval.

## Executable Scope

1. Require a canonical action contract whose category, target, parameters, and effects cannot disguise L2/L3 intent.
2. Replace free-form L2 reopen behavior with supported machine-readable semantics while retaining exact scope, assumptions, expiry, and owner signature checks.
3. Parse GitHub workflow YAML semantically and reject comment-only trigger evidence or job-level permission escalation.
4. Bind attachment publication to the exact verified control and artifact generation.
5. Reject no-op rollback commands and protect all verifier, trust, Evidence, redaction, schema-validation, packaged-policy, and workflow sources.
6. Detect supported provider-secret identifiers after redaction; do not fail every genuinely clean zero-match file.
7. Reject intermediate symlink traversal and FIFO/device/socket input without blocking.
8. Make collect/redact publication transactional or remove incomplete artifacts and control mutations on failure.
9. Persist and deduplicate Operational Action interruption state by bounded action identity, owner, scope, status, and expiry.
10. Upgrade `cryptography` to a patched hash-locked version and update versioned package metadata.

## Acceptance Tests

- Disguised Production/secret/destructive intent cannot return `CONTINUE` with empty effects.
- Supported L2 receipts reuse only while exact scope, assumptions, expiry, and structured reopen state remain valid; unsupported free-form reopen semantics fail closed.
- CI Guard uses parsed YAML values, ignores comments, and rejects write permissions at root or job scope.
- An artifact/control swap after verification cannot publish a stale attachment.
- `/bin/true`, `true`, comments, and placeholders are not accepted as rollback or verification plans.
- Every security-critical source and installed governance copy is protected by Base policy.
- Known provider credential identifiers are redacted or block attachment; ordinary clean text remains eligible.
- Any intermediate symlink or non-regular input fails promptly and creates no external side effect.
- Failed collect/redact leaves no unregistered raw/shareable artifact.
- Repeated identical Operational Action requests reuse one durable pending record instead of emitting duplicate owner prompts.
- `cryptography` resolves to `>=50.0.0` from a hash-locked dependency set.

## Verification Plan

1. Capture RED output from the new hostile regression tests in the DEP.
2. Run targeted authority, CI, merge, Evidence, redaction, governance, and repository-contract suites.
3. Run the complete suite, `sddgov validate`, `sddgov ci verify`, and strict DEP verification.
4. Build wheel/sdist; install the wheel in a fresh environment; run `doctor` and the offline synthetic Muse pilot.
5. Request a fresh independent review. Do not sign, merge, or publish while any P0/P1 remains.

## Non-scope

- Production deployment, migration, secrets, or real user data.
- Stable release publication.
- Changing the approved Product Contract or expanding Agent authority.
