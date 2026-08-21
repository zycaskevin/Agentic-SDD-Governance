# Rollback

rollback_version: 3.0
target: complete 0.2.0rc1 developer-experience and production-readiness batch
rollback_action: git_revert
rollback_ref: 8b36f52b08a151eaa37fe38ff1cd80856a89a0b2
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if bounded/cross-chunk redaction exposes a matched secret, Broker health can report READY without the fixed external controls and valid ledger, the release workflow can publish from a mismatched ref/artifact, managed Governance parity fails, or trusted-Base/exact-tree/autonomy behavior regresses.

## Reversible steps

# Revert immutable implementation commit `8b36f52b08a151eaa37fe38ff1cd80856a89a0b2` through the reviewed Git workflow; keep later Evidence, Gate, and Review commits as audit-only descendants. A disposable no-credential clone proved `git revert --no-commit` restores the exact Base tree without conflict. Never reset or force push protected history.

## Data compatibility

# No product database, customer/patient/payment data, Production schema, or credential migration exists. Reconciliation restores package/governance version experimental.8 and the Base 66-file managed installation. The external append-only Broker ledger must never be reverted, truncated, deleted, or restored backward. If rc1 has already reached a registry, rollback cannot reuse or overwrite that immutable version; an authorized owner must publish a new corrected version or apply the registry's audited yank process.

## Post-rollback verification

# In a disposable credential-free, network-isolated clone, refresh managed Codex governance from the reverted source with `setup-agent --force`, run Doctor, then run unittest, repository validation, and the reverted CI contract. The local drill passed Doctor at experimental.8 with 66 managed files and all 229 Base tests (two sandbox-only skips).
