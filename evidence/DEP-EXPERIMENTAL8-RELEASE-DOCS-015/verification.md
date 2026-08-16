# Verification

## Green command and result

```text
exact current-doc version search: PASS, zero stale matches
pytest: 228 passed, 1 sandbox-only AF_UNIX skip
sddgov validate: PASS
sddgov ci verify: PASS
sddgov ci local-gate: PASS, 229 unittest cases with one sandbox-only AF_UNIX skip
git diff --check: PASS
```

## Before/after evidence

Before: current Traditional Chinese install paths selected experimental.6 and experimental.8 was labelled unreleased/in progress. After commit `b09edcf65a57ce5f01c26eca1419dfa5f3395a7f`: current install paths select experimental.8, machine checksum verification is unchanged, and the release state reflects the completed reviews and hosted verification.

## Remaining limitations

GitHub Release publication, exact final merged-commit provenance, and freshly downloaded asset verification remain external release-transaction steps. Historical documentation and Evidence intentionally retain older version identifiers.
