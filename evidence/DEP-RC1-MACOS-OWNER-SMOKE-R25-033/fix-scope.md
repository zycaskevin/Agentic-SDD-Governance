# Fix Scope

## Smallest sufficient change

Pass the fresh-smoke temporary workspace through the shared fixed-Darwin-alias canonicalizer before using it for AF_UNIX length checks or venv paths. Add a deterministic regression that rehearses the Darwin `/tmp` alias on POSIX.

## Files or components in scope

- `scripts/fresh_wheel_smoke.py`
- `tests/test_release_bundle.py`
- `work-packages/WP-RC1-READINESS-008.md`
- `tests/test_repository_contract.py`
- This R25 DEP and final Gate metadata.

## Explicit non-scope

No change to `owner_cli.py`, the Owner launcher, the eight-file Owner client digest, request/Decision Contract, signed receipt, trust store, signer, TTY flow, runtime custody checks, release publication, or hosted security policy.

## Blast radius

Only the rehearsal workspace spelling changes. Reverting the final immutable product commit restores trusted Base and removes the entire RC1 candidate; external public trust files and the Owner outbox receipt remain outside Git and are not deleted.
