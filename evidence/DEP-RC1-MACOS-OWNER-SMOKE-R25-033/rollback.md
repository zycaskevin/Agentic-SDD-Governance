# Rollback

rollback_version: 3.0
target: RC1 approved Owner authority candidate plus canonical macOS installed-wheel rehearsal
rollback_action: git_revert
rollback_ref: eb1bdae60838135cddf697ab43885229df2cb64c
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Roll back if native macOS still represents the fresh venv inconsistently, the installed Owner runtime fails after canonical rehearsal, the signed decision stops verifying, or any production custody check is weakened.

## Reversible steps

# Revert immutable product commit `eb1bdae60838135cddf697ab43885229df2cb64c` through the reviewed Git workflow. Evidence, Gate metadata, and reviewer receipts remain audit-only records.

## Data compatibility

# R25 changes no receipt, decision, trust-store, signer, or runtime schema. Reversion removes the complete RC1 product candidate and restores trusted Base behavior; external root-owned public trust files and the Owner outbox receipt remain outside Git and are not deleted.

## Post-rollback verification

# Refresh managed Agent governance from the reverted source, run Doctor and repository validation, execute the trusted-Base unittest suite, build/Twine checks, and installed-wheel consumer smoke, then prove the reverted non-audit tree is byte-identical to Base `92f4ba8388ecf1ef1f3407db6c49cef62f6ee196`.
