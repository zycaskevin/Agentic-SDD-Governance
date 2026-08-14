# Rollback

## Trigger

Release documentation points to an unavailable or incorrect artifact, final asset verification fails, or the release-preparation change causes a governance regression.

## Reversible steps

Revert the bounded Release-preparation merge commit. Delete or mark the GitHub Release as withdrawn only if the published assets are incorrect; preserve Issue, CI, DEP, and audit history.

rollback_version: 1.0
target: GitHub merge commit for Release PR #7
command: git revert "$RELEASE_PREP_MERGE_COMMIT"
verify: PYTHONPATH=src python3 -m sddgov.cli ci local-gate .

## Data compatibility

No Production data, user data, schema, credential, permission, or package state is mutated by the repository change. Existing installations remain on their currently installed version.

## Post-rollback verification

Run the 100-test Local Green Gate, validate the previous README and Release Notes links, and confirm the previous GitHub Release assets remain downloadable and checksum-valid.
