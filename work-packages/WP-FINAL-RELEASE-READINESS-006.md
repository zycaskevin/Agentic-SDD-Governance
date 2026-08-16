# Work Package: Final experimental.8 Release Readiness

## References

- Issue: #18 (with #8 and #17 closed in the same implementation)
- Trigger: complete post-merge Security and Autonomy audits of `main`
- Baseline: `main` at `a5c27e306373829eee966222c3915f5a822b190c`
- SDD: `docs/AUTONOMOUS_DEVELOPMENT_V1_2.md`, `docs/HARD_GATES_V1_2.md`, and `docs/EVIDENCE_DRIVEN_SDD.md`
- Risk: L1 regression and release-readiness hardening; GitHub security settings and public Release remain separate external actions

## Objective Contract

- Outcome: close all known P1 security and autonomy findings in one batch, perform one fresh independent review, and publish no intermediate release.
- Success metric: executable contracts, all tracked Proof DEPs, Local Green, package smoke, Codex/Hermes Doctor, offline pilot, and final review are Green with P0=0/P1=0.
- Keep condition: routine L0/L1 engineering and preconfigured public review continue without owner prompts; L2/L3, Secrets, Production, access, cost, and release authority remain fail closed.
- Rollback condition: revert this Work Package if it weakens trusted-Base verification, lets an unbound escalation reach the owner, repeats an already-pending prompt, or accepts unverifiable Evidence.

## Confirmed Red State

1. `sddgov autonomy evaluate` exits zero for `BLOCKED` and `ACTION_REQUIRED`, so shell automation can treat a denied action as success.
2. A Decision Package is not fully bound to the outer request's risk, identity, scope, and L3 operation payload before owner escalation.
3. Necessary UAT is not durable or deduplicated; a machine-verifiable UAT can still prompt, and unrelated Work Packages can be stopped.
4. Operational Action has pending deduplication but no signed terminal completion/cancellation transition.
5. A first-time consumer Base has no trusted protected-file policy or Reviewer store, so its first Governance PR cannot complete Merge verification.
6. Three historical Proof DEPs fail the current portable strict association contract.
7. A malformed CI exemption list raises an unstructured exception.

## Executable Scope

1. Make classifier process exit status match `CONTINUE`, `BLOCKED`, or `ACTION_REQUIRED`.
2. Validate exact category/risk, Decision or Action ID, scope, and complete L3 payload before emitting any Decision Package.
3. Persist Operational Action and Necessary UAT under one exact owner/scope/request lifecycle, prompt once, and continue unrelated work.
4. Import a separate-identity owner-signed resolution receipt for `completed` or `cancelled`; expire deterministically.
5. Add a first-consumer verifier path that uses only the immutable trusted package policy and Repo-external Reviewer public trust, never Candidate bytes.
6. Upgrade the three legacy Proof DEPs to current raw/report/shareable associations and enforce portable strict verification for every tracked Proof DEP.
7. Return a structured fail-closed CI result for invalid exemption entries.
8. Align canonical and packaged Policy, Schema, Skill, templates, documentation, protected-file inventory, Roadmap, and Changelog.

## Acceptance Tests

- `CONTINUE` exits 0, `BLOCKED` exits 1, and `ACTION_REQUIRED` exits 2.
- Risk, identity, scope, or L3 payload mismatch cannot prompt the owner or grant authority.
- Identical Operational Action or Necessary UAT emits at most one owner prompt and persists across calls.
- Machine-verifiable UAT continues without a prompt.
- A trusted exact resolution completes/cancels only the matching owner, scope, class, and request digest.
- One pending L2/L3/Operational/UAT request does not stop unrelated Work Packages.
- A first consumer can pass protected-file verification using trusted verifier policy plus separate-identity external Reviewer trust; Candidate policy/trust cannot alter the decision.
- A partially governed or malformed Base does not reuse first-consumer bootstrap.
- Every tracked Proof DEP passes `evidence verify --strict --portable`.
- Invalid CI exemption entries return structured `ok: false` without an exception.
- Canonical and packaged Governance resources remain byte-identical.
- Full tests, validate, CI Guard, Local Green, build, fresh install, Doctor, offline pilot, independent Review, and exact Merge Gate pass.

## Release Rule

Do not create a tag or Release until one final fresh Reviewer reports P0=0/P1=0, external GitHub security controls are enabled and read back, exact-commit provenance is signed or attested, and downloaded assets plus SHA-256 checks are independently verified. If a P0/P1 remains, fix the batch and repeat the final review without publishing an intermediate candidate.

## Non-scope

- Production deployment, credentials, Billing, real user data, or destructive operations.
- Activating GitHub Rulesets, security features, or publishing a Release without the explicit external-action authorization.
- Expanding L2/L3 authority or weakening Evidence, rollback, trusted verifier, or independent Review gates.
