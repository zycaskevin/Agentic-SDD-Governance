# Verification

## Green command and result

PASS on the exact working tree before review:

- Full suite and Local Green Gate: 190/190 tests PASS on macOS, including the real AF_UNIX broker path with no skip.
- `sddgov validate`: PASS.
- `sddgov ci verify`: PASS.
- Existing five strict DEPs: full and portable verification PASS.
- Wheel and sdist build: PASS.
- Fresh Python 3.11 wheel install: `pip check` PASS.
- Fresh Codex and Hermes installs: `doctor` PASS with 63 managed files each.
- Offline synthetic Muse pilot: PASS with `network_used=false` and `real_data_used=false`.

Package digests:

- wheel SHA-256: `3574f51dd39aa57420a18796898135a746efab6a9614df25aca9414b37d4d7ef`
- sdist SHA-256: `6338f28bea66e62821c3723d3795278bb7696bd7ffb9352a00716a1910e71547`

Fresh install root: `/private/tmp/sdg-exp8-r5-final-wheel-NrC9PX` (local, disposable proof only).

## Before/after evidence

Before: Hosted run `31919258947` reached the Base-controlled Merge policy and rejected the v2-only gate with `rollback record is missing or incomplete`. After: candidate tests prove that one exact legacy v1 record is accepted only as non-executing migration data; wrappers, chaining, observational commands, alternate verification, duplicates, extra fields, and placeholders are blocked. Exact Base-verifier compatibility and Hosted proof remain gated on fresh independent review and the final audit receipt.

## Remaining limitations

One newly authorized Hosted Run is available after local and independent proof. No further rerun is authorized if that run fails.
