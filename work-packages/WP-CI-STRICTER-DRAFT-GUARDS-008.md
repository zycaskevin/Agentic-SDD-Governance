# Stricter Draft Guard Work Package

## References

- Issue: #44
- SDD: `.agentic-sdd-governance/docs/CI_COST_GUARD.md`
- Risk: L1

## Objective Contract

- Outcome: CI Cost Guard accepts a deliberately bounded PR-only conjunction only when every execution path requires `github.event.pull_request.draft == false`.
- Success metric: the VoiceKey PR #48 opt-in condition passes, while missing, bypassable, negated, dynamic, or multi-event Draft guards remain rejected by executable tests.
- Guardrails: no general GitHub expression evaluator; no acceptance, permission, timeout, concurrency, event, or hosted-budget weakening.
- Keep condition: the full repository test suite, validation, CI Guard, built-wheel isolated verification, and strict portable DEP verification remain Green.
- Rollback condition: any unsafe expression reaches Green, an existing rejected fixture becomes accepted, or the runtime cannot verify the exact VoiceKey condition from an isolated wheel.

## Scope

- In scope: `src/sddgov/ci_guard.py`, targeted tests, mirrored CI Cost Guard documentation/resources, version metadata, Work Package, and one full DEP.
- Non-scope: arbitrary expression evaluation, VoiceKey product behavior, billing policy, self-hosted runner lifecycle, unrelated governance policy/schema changes, or public release before an exact artifact gate.
- Dependencies: Issue #44 and VoiceKey Issue #43 / PR #48 as the downstream reproducer.
- Evidence requirement: `DEP-CI-STRICTER-DRAFT-GUARDS-016`, full Red → Evidence → Fix → Green → Proof.
- Verification plan: targeted Cost Guard Red/Green tests; full unit suite; `sddgov validate`; `sddgov ci verify`; `sddgov ci local-gate`; strict portable DEP; isolated wheel install; exact VoiceKey workflow verification; independent protected-file review.

## Claim

- Agent: Codex main builder
- Claimed at: 2026-08-22T15:08:00Z
- Expires at: completion or supersession of Issue #44
