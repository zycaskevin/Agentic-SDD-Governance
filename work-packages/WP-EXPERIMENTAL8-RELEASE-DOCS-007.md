# Experimental.8 Release Documentation Work Package

## References

- Issue: #20
- SDD: `RELEASE_NOTES.md`, `docs/USER_GUIDE.zh-TW.md`
- Risk: L0

## Objective Contract

- Outcome: every current public installation path selects `v0.2.0-experimental.8` and the release state matches the verified delivery state.
- Success metric: the scoped current docs contain no experimental.6 install command and no experimental.8 `unreleased` or `in progress` marker.
- Guardrails: documentation and release metadata only; no runtime, Policy, Schema, authority, workflow, dependency, or security-control changes.
- Keep condition: repository tests, validation, CI Guard, and portable DEP verification remain Green.
- Rollback condition: any changed instruction downloads a different tag, weakens machine checksum verification, or makes a delivery claim unsupported by the final evidence.

## Scope

- In scope: `README.zh-TW.md`, `docs/USER_GUIDE.zh-TW.md`, `RELEASE_NOTES.md`, `CHANGELOG.md`, and `docs/ROADMAP.md`.
- Non-scope: source code, packaged Governance resources, GitHub workflow, L0-L3 authority, release assets, and Production operations.
- Dependencies: PR #19 merge, Issue #20, final P0=0/P1=0 reviews, successful hosted run `31945289264`.
- Evidence requirement: `DEP-EXPERIMENTAL8-RELEASE-DOCS-015` using the Red → Evidence → Fix → Green → Proof loop.
- Verification plan: exact version-reference search, repository tests, `sddgov validate`, `sddgov ci verify`, strict portable DEP verification, and one hosted verification for this Work Package.

## Claim

- Agent: Codex main agent
- Claimed at: 2026-08-16T11:54:48Z
- Expires at: completion of Issue #20
