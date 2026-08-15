# Rollback

rollback_version: 2.0
target: closed category request-schema enforcement for experimental.8
rollback_action: git_revert
rollback_ref: HEAD
verify_action: python_module
verify_module: pytest

## Trigger

The closed schema rejects a previously valid, single-authority request or causes an unrelated autonomy regression that cannot be corrected within the same Work Package.

## Reversible steps

Revert the exact experimental.8 classifier commit with `git revert`; do not restore the vulnerable candidate as a release or Production gate.

## Data compatibility

No data-format or persistent-store migration is introduced. Existing decision and approval records remain readable.

## Post-rollback verification

Run the full pytest module and confirm the prior candidate remains unreleased and fail-closed while a corrected replacement is prepared.
