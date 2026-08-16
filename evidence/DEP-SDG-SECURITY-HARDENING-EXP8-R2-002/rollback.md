# Rollback

rollback_version: 2.0
target: bounded experimental.8 second-round security hardening
rollback_action: git_revert
rollback_ref: 822ed753ff87d8eed2e3256cf8ae30b2a125e3c4
verify_action: python_module
verify_module: pytest

## Trigger

# Rollback if closed-envelope classification blocks authority-free routine work, no-clobber publication loses a later writer, strict DEP verification accepts a stale generation, or the rollback v2 parser accepts free-form execution.

## Reversible steps

# Revert the bounded candidate commit through the reviewed Merge path. Keep raw DEP evidence local and retain the failed candidate for diagnosis. Consumers remain on experimental.7 until a corrected candidate is independently reviewed.

## Data compatibility

# No Production data, migration, provider credential, or real Muse data is changed. Rollback v1 prose remains historical evidence but is intentionally not accepted as a current Merge authorization record.

## Post-rollback verification

# Run the full test suite, repository validation, CI Guard verification, strict full/portable DEP verification, fresh wheel Codex/Hermes doctor, and offline synthetic Muse pilot. Confirm later-writer fixtures remain byte-for-byte unchanged.
