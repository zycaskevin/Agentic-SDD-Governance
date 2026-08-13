# Work Package: Traditional Chinese Documentation and Public Readiness

## References

- Issue: #1
- SDD: Agentic SDD Governance documentation and release contract
- Risk: L1 for documentation and public-safety review; changing repository visibility remains L2 and out of scope.

## Objective Contract

- Outcome: A new user can install and operate Agentic SDD Governance from Traditional Chinese documentation, while the owner can make an informed public-release decision.
- Success metric: README entrypoint, complete Traditional Chinese guide, public-release checklist, security policy, and contribution guide exist with verified relative links and commands.
- Guardrails: Preserve progressive disclosure; do not expose raw evidence, credentials, or unrelated local changes; do not change GitHub visibility.
- Keep condition: Documentation matches executable CLI help and the installer's managed-file behavior.
- Rollback condition: Revert only the files introduced or edited by this Work Package.

## Scope

- In scope: `README.md`, `README.zh-TW.md`, Traditional Chinese usage and public-readiness documents, `SECURITY.md`, `CONTRIBUTING.md`, and third-party notice clarification.
- Non-scope: Repository visibility, Git history rewriting, Release mutation, unrelated in-progress development, and public marketing claims.
- Dependencies: Existing v0.2.0 experimental CLI, installer, Evidence workflow, CI Cost Guard, Apache-2.0 license, and baseline provenance.
- Evidence requirement: CLI help inspection, targeted worktree/history credential scan, tracked-file review, link check, and repository validation.
- Verification plan: Run documentation checks, targeted tests or Local Green Gate where the unrelated working tree permits, and `sddgov validate`.

## Claim

- Agent: Codex
- Claimed at: 2026-08-13T04:23:47Z
- Expires at: 2026-08-13T06:23:47Z
