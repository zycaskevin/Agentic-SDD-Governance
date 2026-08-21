# Rollback

rollback_version: 3.0
target: complete governed 0.2.0rc1 R3 readiness implementation
rollback_action: git_revert
rollback_ref: a4ae82a3fdaf494f102c9ca1f6386f59a3c93cdc
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if exact protected-environment admission can be bypassed, CI permission
# exceptions grant more than their exact job/field, Broker deadline or cleanup
# fails, Quick Demo can mask a nested FAIL, streaming redaction exposes a
# private-key body, package provenance diverges, or full validation regresses.

## Reversible steps

# Revert immutable implementation commit
# `a4ae82a3fdaf494f102c9ca1f6386f59a3c93cdc` through the reviewed Git workflow;
# keep later Evidence, Gate, and Review commits as audit-only descendants. Never
# reset or force-push protected history.

## Data compatibility

# No product database, credential, Production schema, customer/patient/payment
# data, or external Broker ledger migration exists. Reconciliation restores
# governance version experimental.8 and the Base 66-file managed installation.
# Historical proof is not reusable authority. If rc1 reaches a registry, use a
# new corrected version or the registry's authorized, audited yank process.

## Post-rollback verification

# In a disposable credential-free clone, revert the implementation, assert the
# complete candidate tree equals Base
# `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`, run `setup-agent --force`, require
# Doctor experimental.8 with 66 managed files, then run the full Base unittest,
# repository validation, and CI contract.
