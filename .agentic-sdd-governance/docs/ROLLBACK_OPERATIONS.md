# Rollback v3, Squash Merge, and Break-Glass Recovery

Rollback v3 is intentionally narrow: pre-Merge proof accepts one immutable, full-SHA, single-parent implementation commit and a closed reconciliation/verification sequence. It does not accept a merge commit, symbolic ref, shell wrapper, force-push plan, or caller-selected bypass.

## Why single-parent is required

A single-parent commit has one unambiguous before tree. The trusted verifier can therefore simulate its inverse at the reviewed Head and prove that the non-Evidence result equals the exact trusted Base. A merge commit has multiple possible parents and would require caller-selected mainline semantics, which is too ambiguous for the current contract.

If the pre-Merge verifier rejects a rollback record, do not override it. Restructure the feature branch or split the Work Package until the contract is provable.

## Squash-compatible feature workflow

Use this layout before review:

```text
trusted Base
  └─ one atomic implementation commit       <- rollback_ref
       └─ Evidence/rollback binding commit   <- Evidence-only
            └─ Merge gate/review receipts    <- audit-only
```

1. Before creating signed review artifacts, combine every non-Evidence change for the Work Package into one atomic, single-parent implementation commit on the feature branch.
2. Run Local Green on that commit and record its full 40-character SHA as `rollback_ref` in the later `rollback.md` v3 record.
3. Between the atomic implementation commit and the reviewed Head, every descendant may change only `evidence/`. After that reviewed Head is fixed, later audit commits may change only `.sddgov/merge-gate.json` or `.sddgov/reviews/`. Any product, code, configuration, documentation, or out-of-window audit-path change requires a new implementation commit and a new rollback proof/review.
4. Configure the repository to use squash-and-merge for governed PRs. Disable merge commits for this workflow; a force push to the protected branch is not a rollback method.
5. GitHub creates a new single-parent squash commit on the protected branch. Immediately record the platform-generated squash SHA, source PR, reviewed Head, and pre-Merge `rollback_ref` in the post-Merge audit record. The tree is the reviewed PR result, while the actual incident revert target is now the squash SHA.

For a post-Merge rollback, revert the protected-branch squash SHA, not the feature-branch SHA:

```bash
protected_branch="${SDDGOV_PROTECTED_BRANCH:?set the protected branch}"
git fetch --prune origin "$protected_branch"
git switch -c incident/INC-YYYY-NNN "origin/$protected_branch"
git revert --no-commit <full-squash-merge-sha>
```

Then inspect the staged inverse, reconcile managed SDG files from the reverted source, run `sddgov doctor`, the declared Python test module, and the service health checks appropriate to the repository. Commit and merge the recovery through the normal protected emergency-PR path.

Squash merging does not weaken the pre-Merge proof. It does mean the post-Merge audit system must retain the mapping from the reviewed atomic commit to the platform-created squash commit.

## Historical proof is not reusable authority

A DEP in `proof` phase is an immutable historical record, not a standing authorization. The Merge gate binds the exact reviewed Head, Base, executable digest, rollback record, and review metadata. Reverting the implementation commit changes the candidate Head and tree, so the previous gate fails its exact-Head check and cannot approve the reverted or superseding state. Preserve the old DEP and gate for audit; create fresh Evidence, rollback proof, gate metadata, and review for the new Head. Never delete historical Evidence to make a new candidate appear pre-approved.

## Routine rollback failure

If the revert conflicts or Doctor/tests do not return Green:

1. stop and keep the failed work only on the incident branch;
2. collect the conflict, exact refs, and failed verification into local raw Evidence;
3. create a new recovery Work Package and redacted DEP;
4. repair the inverse as a reviewed forward commit rather than rewriting protected history;
5. require independent review when protected files or security controls are affected.

Do not use `git reset --hard`, a protected-branch force push, acceptance-test weakening, or deletion of Evidence to make a rollback appear Green.

## Break-glass incident recovery

Break glass is an external repository/operations authority path for an active incident, not a hidden SDG verifier mode. SDG intentionally provides no `--skip-rollback`, `--trust-me`, or mock approval flag.

Use break glass only when waiting for the normal protected PR path would materially increase harm:

1. Declare an incident ID, commander, affected trust domain, exact Production impact, and time-bounded emergency authority. Before an Agent or operator stops deployments/executors or invokes any emergency ruleset bypass, obtain and durably record explicit L3 human approval outside Agent control. The approval record must identify every approver, incident ID, exact action and scope, protected-branch SHA, issue time, and expiry. Use two-person control for regulated, patient or customer data, payment, or key compromise incidents. If the required approval is unavailable, an Agent must not perform the L3 action.
2. Only within that recorded scope and unexpired approval, stop deployments and autonomous executors. Preserve the exact protected-branch SHA, failing release/deployment identifier, runtime context, Broker status, and relevant audit logs.
3. Prefer reverting the recorded full squash SHA on a new incident branch. Never force push the protected branch.
4. Review the recovery diff and run every locally available Doctor, test, security, data-integrity, and service-health check. Missing checks are recorded as limitations, not silently marked PASS.
5. Use the repository platform's separately controlled, time-bounded emergency ruleset bypass only if the normal emergency PR cannot operate and the recorded L3 approval explicitly covers that bypass and remains unexpired. Record the administrator identities and platform audit event. Do not edit SDG policy, the trusted Base verifier, Review receipts, or branch rules in the recovery commit to manufacture approval.
6. Restore the normal ruleset and revoke emergency credentials immediately after containment. Confirm it by read-back.
7. Within 24 hours, create a normal governed follow-up PR containing the complete redacted incident DEP, the squash-SHA mapping, the final recovery diff, verification results, remaining limitations, and key rotation/revocation evidence when relevant.

If someone has already force-pushed the protected branch, freeze writes, preserve reflogs/platform audit logs, restore the last independently verified tree as a new reviewed forward commit where possible, rotate any possibly exposed trust roots, and treat the event as a security incident. Do not erase the event by rewriting history again.
