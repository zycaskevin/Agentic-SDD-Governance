# Experimental.9 Release Notes Privacy Work Package

## References

- Issue: #46
- SDD: `RELEASE_NOTES.md`
- Risk: L1

## Objective Contract

- Outcome: public experimental.9 notes describe the verified Cost Guard result
  without naming a downstream repository, pull request, or unpublished state.
- Success metric: the public notes retain installed-wheel verification while
  containing no downstream-specific identifier or reproducer detail.
- Guardrails: wording, Evidence, and the audit-only `.sddgov/merge-gate.json`
  binding; no runtime, version, authority, workflow, dependency, or Cost Guard
  logic change.
- Keep condition: full tests, validation, CI Guard, and Local Green stay Green.
- Rollback condition: the wording again exposes downstream-specific context or
  weakens the factual installed-wheel claim.

## Scope

- In scope: `RELEASE_NOTES.md`, this Work Package,
  `DEP-EXP9-RELEASE-NOTES-017`, and `.sddgov/merge-gate.json` as the audit-only
  binding for the exact reviewed revision.
- Non-scope: runtime code, policies, schemas, workflows, trust, downstream
  source, remote tag, and Release publication.
- Evidence requirement: Red -> Evidence -> Fix -> Green -> Proof.
- Verification plan: exact public-text search, full tests, validation, CI
  verification, Local Green, strict portable DEP, and fresh exact review.

## Claim

- Agent: Codex main agent
- Claimed at: 2026-08-22T15:54:00Z
- Expires at: completion of Issue #46
