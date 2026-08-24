# Reproduction

## Expected

Only the exact Base-bootstrap legacy record is eligible; every rollback resolves to a full existing immutable candidate-range commit; unknown standalone content is rejected.

## Actual

Three hostile tests fail: no v1 discriminator exists, `HEAD` remains accepted, and a nonexistent full hexadecimal ref reaches `MERGE_READY`. A standalone non-comment command is also ignored.

## Deterministic steps

1. Call `_real_rollback` with the canonical legacy v1 record without Base context.
2. Call `_real_rollback` with v2 `rollback_ref: HEAD` and `rollback_ref: deadbee`.
3. Commit a v2 record containing forty `f` characters, create a valid Gate/Receipt, and run `verify_merge`.
4. Append a non-comment standalone shell-looking line to the legacy record.
5. Observe acceptance where all four cases must fail closed.

## Environment and preconditions

PR #12 branch `fix/security-hardening-exp8`, Base `f44cb5f4897f6c821f817fcf178581b43777163a`, Head `3c11f977f1a36d87511047437d8e4f631b6ddf9e`, local synthetic Git repositories only.
