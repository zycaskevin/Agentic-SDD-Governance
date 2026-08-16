# Work Package: Release Readiness Post-merge Hardening

## References

- Issue: #15
- Trigger: fresh post-merge audit of PR #14
- Baseline: `main` at `ce08f48c5d7c4232e9c0154dabb3b43c63b920c1`
- SDD: `docs/HARD_GATES_V1_2.md`, `docs/CI_COST_GUARD.md`, and `docs/AUTONOMOUS_DEVELOPMENT_V1_2.md`
- Risk: L1 regression hardening; GitHub Ruleset activation remains a separate Operational Action

## Objective Contract

- Outcome: a reviewed change has an executable Green rollback post-condition, and one Work Package cannot automatically consume both a PR run and a post-merge `main` run.
- Success metric: rollback reconciliation, Doctor, declared tests, CI event controls, Policy copies, and permanent regressions all pass locally before one bounded hosted run.
- Keep condition: trusted Base verification, signed independent Review, strict DEP, Local Green, and public review-sharing safety boundaries remain unchanged.
- Rollback condition: revert this Work Package if it weakens the trusted verifier, suppresses the required PR check, executes candidate code in the privileged hosted job, or cannot restore the previous healthy installed-governance state.

## Confirmed Red State

1. Reverting PR #14 implementation commit `fd691a7a069fbaa0f5d5f17886524a29f1ba17a4` restores the non-Evidence tree to its exact Base but leaves `.sddgov/project.json` at experimental.8 while the installed manifest returns to experimental.7; `sddgov doctor` fails.
2. Work Package #13 consumed two successful hosted jobs: PR run `31931408005` and post-merge `main` push run `31931428520`.
3. CodeRabbit found six non-blocking review-sharing wording and permanent-test gaps; the post-merge audit found stale Roadmap and public-release-checklist statements.
4. GitHub reports `main` as unprotected and repository rulesets as empty. This is recorded as a Release blocker, but changing GitHub authority remains outside this L1 code mutation until explicitly authorized.

## Executable Scope

1. Introduce a closed declarative rollback record that includes deterministic installed-governance reconciliation, Doctor, and an allowlisted Python test module.
2. Run the declared rollback post-condition in an isolated local drill when local Merge verification is enabled; the privileged hosted verifier continues to avoid candidate execution and relies on the signed independent Review plus static rollback proof.
3. Extend CI Cost Guard so `post_merge_verification: manual_only` rejects automatic `push` workflows, while keeping the one trusted `pull_request_target` check and optional `workflow_dispatch` Release verification.
4. Remove the automatic `push: main` Governance trigger.
5. Clarify that public routine review is pre-authorized, while an exact Private Repo/Reviewer decision is a separate authorization path.
6. Align vendor, destination, MFA, OAuth, account-permission, other-access, and cost wording across policy, Schema, Skill routes, guides, packaged resources, installed copies, and regression tests.
7. Correct stale Roadmap and Public Release Checklist statements.
8. Correct PR #14 rollback and reproduction Evidence without altering raw Evidence.

## Acceptance Tests

- The PR #14 rollback drill performs the declared reconciliation and returns Doctor plus the declared Python test module to Green.
- Removing reconciliation or Doctor from the rollback contract fails closed.
- Hosted verification with `post_merge_verification: manual_only` rejects every automatic `push` event.
- The Governance workflow has one automatic PR route and one manual route, with no automatic post-merge route.
- Candidate code remains data-only in the privileged `pull_request_target` job.
- Review-sharing policy retains the exact minimum public payload and forbidden sensitive classes.
- Private Repo sharing cannot inherit public routine pre-authorization; an exact recorded Repo/Reviewer decision is described as a separate route.
- New destination, MFA, OAuth scope, account permission, other access, vendor, or cost cannot use routine pre-authorization.
- Canonical, packaged, and installed governance copies remain byte-consistent.
- Full tests, strict DEP, Local Green, build, fresh Codex/Hermes install, independent Review, and exact Merge Gate pass.
- No hosted run occurs while the PR is Draft; Ready triggers at most one hosted run and Merge triggers none.

## Non-scope

- Changing GitHub repository Rulesets, branch protection, Billing, budgets, runners, or credentials.
- Publishing a public Release.
- Weakening tests, Evidence, Review signatures, Production, Secret, data, permission, or L2/L3 boundaries.
