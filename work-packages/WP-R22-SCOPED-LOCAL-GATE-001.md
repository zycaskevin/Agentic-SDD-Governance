# Work Package: R22 Scoped Local-Green Gate

## References

- Predecessor: `DEC-RC1-APPROVER-AUTHORITY-R22`
- SDD: `docs/R22_SCOPED_VALIDATION.md`
- Risk: L2 security-policy change; offline foundation only.

## Objective Contract

- Outcome: define and test an exact, fail-closed classifier that distinguishes
  R22 authority changes from unrelated feature changes.
- Success: authority inputs, verifier code, packaged governance resources,
  decision artifacts, and Gate configuration always require R22; an exact
  AF27-only path set does not.
- Keep: the existing unconditional R22 Local-Green command remains active.
- Non-scope: enabling scoped execution, changing the current CI contract,
  signing, trust-store provisioning, production, release, or deployment.

## Claim

- Owner direction: validate R22 only when R22-related security files change.
- Builder: Codex.
- Status: offline foundation in progress; no policy activation is enabled.
