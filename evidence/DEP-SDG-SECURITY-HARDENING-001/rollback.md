# Rollback

rollback_version: 1.0
target: Security hardening candidate on fix/security-hardening-exp7
command: git revert the exact merged security-hardening commit or merge commit
verify: python3 -m unittest discover -s tests -v and python3 -m sddgov.cli validate .

## Trigger

Unexpected false-positive blocking, incompatible installed-project migration, or a verifier isolation defect found before real adoption.

## Reversible steps

Revert the exact bounded change. Keep raw Evidence local, retain the signed audit trail, and restore the last independently verified experimental.6 release artifact while a corrected candidate is prepared.

## Data compatibility

No product or Production data migration is performed. L2 records created by this candidate are additive signed-envelope records; do not rewrite or downgrade them during rollback.

## Post-rollback verification

Run the full test suite, repository validation, CI Cost Guard verification, and an experimental.6 fresh-install doctor check. Confirm the reverted workflow and documented trust boundary match the selected release before any new PR is evaluated.
