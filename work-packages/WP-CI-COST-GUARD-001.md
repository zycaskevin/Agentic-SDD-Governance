# Work Package: CI Cost Guard

## References

- Issue: local governance work package
- SDD: `docs/CI_COST_GUARD.md`
- Risk: L1

## Objective Contract

- Outcome: prevent Agents from using GitHub-hosted Actions as a remote debugging loop.
- Success metric: local Green Gate passes before Push; automatic workflows cancel stale runs, skip Draft PR runners, use read-only permissions, and bound every hosted job with a timeout.
- Guardrails: do not weaken acceptance checks, required evidence, deployment gates, or product behavior.
- Keep condition: CI verification remains deterministic and cheaper than the current baseline.
- Rollback condition: revert workflow controls if they prevent required branch checks or cancel a non-replaceable operation.

## Scope

- In scope: canonical policy, contract Schema/template, CLI verification/local gate, Skill route, tests, and safe workflow adapters.
- Non-scope: GitHub Billing mutation, public/private repository changes, self-hosted runner installation, deployment behavior, and schedule-frequency changes.
- Dependencies: existing Policy Kernel, Profile, and repository-local test commands.
- Evidence requirement: targeted tests, full local suite, `sddgov validate`, and static workflow verification.
- Verification plan: unit fixtures plus clean local execution against the repository contract.

## Claim

- Agent: Codex
- Claimed at: 2026-08-10
- Expires at: completion of this bounded implementation pass
