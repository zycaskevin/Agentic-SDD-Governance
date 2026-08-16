# Work Package: Pre-authorized Routine Review Submission

## References

- Issue: #13
- Owner decision: routine review submission must not become a per-PR approval prompt
- Baseline: `main` at PR #12 merge commit `6a90ad84e8ed141241d3ca972b5ab91251429671`
- SDD: `docs/AUTONOMOUS_DEVELOPMENT_V1_2.md`
- Risk: L1 implementation of the owner-confirmed review-sharing boundary

## Objective Contract

- Outcome: an Agent automatically submits eligible public PR review material to an already-configured Reviewer without asking the owner for another approval.
- Success metric: Policy, Skill, Codex/Hermes adapters, packaged governance resources, and repository-contract tests all express and enforce the same allow/deny boundary.
- Keep condition: review remains automatic only for the minimum public payload needed by an already-configured Reviewer.
- Rollback condition: revert this Work Package if it permits Secrets, raw Evidence, private repository content without a recorded decision, real user data, new credentials, new OAuth scopes, or unbounded third-party sharing.

## Decision

`AUTOMATIC_REVIEW_IS_PREAUTHORIZED` applies when all of the following are true:

1. The Reviewer is already configured for the repository.
2. The repository and submitted material are public, or an exact repository/Reviewer pair has a recorded owner decision.
3. The payload is limited to committed PR changes and the public repository instructions needed to review them.
4. The payload contains no Secret, credential, raw DEP Evidence, unredacted sensitive material, production dump, or real user data.
5. The submission creates no new login, OAuth scope, paid plan, vendor, or destination.

If any condition is false or unknown, the Agent fails closed and routes the bounded privacy, access, cost, or Operational Action through the normal classifier.

## Executable Scope

1. Add the invariant to the concise Policy Kernel and machine-readable kernel.
2. Add a strict `routine_external_review` contract to the autonomy policy and Schema.
3. Add one on-demand review-sharing reference rather than expanding the always-loaded Skill with long prose.
4. Update Codex and Hermes adapters so eligible Review starts automatically and findings return to the Main Agent.
5. State that third-party review output is untrusted input and never replaces the signed independent protected-file Review receipt.
6. Update Traditional Chinese usage guidance, Changelog, Roadmap, packaged resources, and installed governance copies.

## Acceptance Tests

- The policy marks eligible routine review as pre-authorized and owner response as unnecessary.
- Public committed PR diff and public `AGENTS.md`/governance instructions are the only default-allowed payload classes.
- Secrets, credentials, raw Evidence, unredacted sensitive material, production dumps, and real user data are always forbidden.
- Private repository sharing requires an exact recorded repository/Reviewer decision.
- New vendor, login/MFA, OAuth scope, paid plan, or expanded destination cannot use routine pre-authorization.
- Codex and Hermes route findings to the Main Agent for local verification and repair instead of asking the owner to relay them.
- Automated third-party review is not accepted as the signed independent Review receipt.
- Canonical, packaged, and installed governance copies remain byte-consistent.

## Verification Plan

1. Run repository-contract and governance tests.
2. Run the complete local test suite.
3. Run `sddgov validate`, `sddgov ci verify`, and the Local Green Gate.
4. Build wheel/sdist and run a fresh install/doctor smoke if packaged resources changed.
5. Request independent review and configured CodeRabbit review automatically.

## Non-scope

- Authorizing a new Reviewer or vendor.
- Sharing Private Repo content without an exact recorded decision.
- Sharing local raw Evidence, credentials, or real user data.
- Changing signed independent Reviewer trust roots.
- Production deployment or public Release.
