# Rollback

rollback_version: 3.0
target: complete 0.2.0rc1 readiness implementation and CodeRabbit review fixes
rollback_action: git_revert
rollback_ref: 387b7d6052068ada9d07a9fbaadaf35758c42a5c
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if the Broker can leave its bound fixed-path socket after normal service signals, the release bundle can omit or substitute a locked runtime dependency, fresh-wheel smoke reaches a package index, redaction publishes an oversized logical line, the environment preflight accepts broad or self-approved release authority, or any trusted-Base, exact-tree, nonce, signature, or digest boundary regresses.

## Reversible steps

# Revert immutable implementation commit `387b7d6052068ada9d07a9fbaadaf35758c42a5c` through the reviewed Git workflow; retain this Evidence commit and later Gate/Review records as audit-only descendants. Reconcile managed files from the reverted source. Never reset, force push, delete historical DEP records, or roll back the external append-only Broker nonce ledger.

## Data compatibility

# No product database, customer, patient, payment, Production schema, credential, or irreversible data migration is included. Reconciliation restores version experimental.8 and the Base managed-governance set. If 0.2.0rc1 has already reached a registry or GitHub Release, its immutable files cannot be overwritten; use an authorized corrected version or the registry's audited yank process.

## Post-rollback verification

# In a disposable credential-free clone, apply `git revert --no-commit 387b7d6052068ada9d07a9fbaadaf35758c42a5c`, confirm the inverse is conflict-free and returns every non-Evidence path to Base, refresh managed Codex governance from the reverted source, run Doctor, then run unittest, repository validation, and the reverted CI contract. The trusted static rollback verifier performs this exact-tree proof without executing candidate scripts.
