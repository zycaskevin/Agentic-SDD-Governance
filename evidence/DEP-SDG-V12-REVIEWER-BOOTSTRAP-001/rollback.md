# Rollback

## Trigger

The Reviewer CLI exposes private key bytes, permits Repo-local/broadly readable keys, overwrites an identity, signs a dirty or mismatched revision, or weakens the existing independent Merge verification boundary.

## Reversible steps

Revert the bounded Reviewer bootstrap commit. Preserve the previous fail-closed Merge verifier and public receipt schemas. Remove no external Reviewer identity automatically; the owner-controlled host retains or revokes it under its local policy.

rollback_version: 1.0
target: bounded Reviewer bootstrap/signing commit in PR #5
command: git revert "$REVIEWER_BOOTSTRAP_COMMIT_SHA"
verify: PYTHONPATH=src python3 -m unittest discover -s tests -v

## Data compatibility

No Production or application data format changes. Existing public trust files and signed receipts remain auditable but the reverted CLI will no longer create new ones.

## Post-rollback verification

Run the pre-fix complete suite, `sddgov validate`, `sddgov ci verify`, and existing Merge Gate adversarial tests. Confirm the verifier still rejects missing, forged, stale, or candidate-controlled Review receipts.
