# Fix Scope

## Smallest sufficient change

Rebuild the RC1 candidate from Base with the R2 implementation plus verified
CodeRabbit corrections, keeping exactly one non-Evidence implementation commit.

## Files or components in scope

- Protected release workflow and CI Cost Guard schema/verifier/templates.
- Broker request deadline and bound-socket cleanup.
- Quick Demo verdict composition and streaming private-key state.
- English/Traditional Chinese installation and release transaction guidance.
- Governance version event continuity and Work Package Issue binding.
- Regression tests, packaged/installed governance parity, and this R3 DEP.

## Explicit non-scope

- No TestPyPI/PyPI/GitHub Release publication or exact release tag.
- No GitHub environment, repository ruleset, secret, or Trusted Publisher setup.
- No real Owner/reviewer key, root Broker install, nonce, Production operation,
  patient/customer/payment data, WSL2 rehearsal, or macOS rehearsal.
- No rewrite of PR #23/#24, their review threads, or any prior DEP attachment.
- No protected-file receipt created by the builder.

## Blast radius

Release and CI authorization paths, L3 availability, evidence redaction, and
onboarding are affected. Product runtime behavior and external systems are not.
The release remains Draft and fail-closed until independent review and the
three protected environments exist.
