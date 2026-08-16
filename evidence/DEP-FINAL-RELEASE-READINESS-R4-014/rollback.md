# Rollback

rollback_version: 3.0
target: final CodeRabbit P1 closure and Python 3.10 compatibility batch
rollback_action: git_revert
rollback_ref: f03af448f453859d02e63f501fc0ad9aa62ae5ac
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if fresh independent review finds a P0/P1 authority, trust-bootstrap, process-routing, durable-state, or declared-runtime regression attributable to this exact atomic commit.

## Reversible steps

# Revert the immutable atomic commit through the reviewed Git workflow. In a disposable clone, `git revert --no-commit f03af448f453859d02e63f501fc0ad9aa62ae5ac` completed without conflict and restored the exact trusted-Base non-Evidence/non-audit tree.

## Data compatibility

# Existing schema-1.1 terminal action stores remain readable after rollback. A non-empty schema-1.0 legacy store continues to fail closed and requires explicit archival plus exact action re-queue; no Production data migration is involved.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source with `setup-agent --force`, run Doctor, then run the declared unittest module and affected full verification matrix. The disposable drill passed Doctor with 64 managed files and all 205 reverted tests without failure (one local sandbox-only AF_UNIX skip).
