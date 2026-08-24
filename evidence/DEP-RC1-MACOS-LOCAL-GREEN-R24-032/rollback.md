# Rollback

rollback_version: 3.0
target: RC1 approved Owner authority candidate plus cross-platform verification fix
rollback_action: git_revert
rollback_ref: d7360248f7d77f2cf363747f6222316448a818bb
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Roll back if Darwin path fixtures again bypass the intended assertion boundary, a configured Local Green waits on its own serialization lock, the fixed trust source or signed decision stops verifying, or any production fail-closed check is weakened.

## Reversible steps

# Revert immutable product commit `d7360248f7d77f2cf363747f6222316448a818bb` through the reviewed Git workflow. Evidence, Gate metadata, and reviewer receipts remain audit-only records.

## Data compatibility

# No receipt, decision, trust-store, or runtime data schema changes are introduced by R24. Reversion removes the complete RC1 product candidate and restores trusted Base behavior; external root-owned public trust files and the Owner outbox receipt remain outside Git and are not deleted.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor and repository validation, execute the trusted-Base unittest suite, build/Twine checks, and installed-wheel consumer smoke, then prove the reverted non-audit tree is byte-identical to Base `92f4ba8388ecf1ef1f3407db6c49cef62f6ee196`.
