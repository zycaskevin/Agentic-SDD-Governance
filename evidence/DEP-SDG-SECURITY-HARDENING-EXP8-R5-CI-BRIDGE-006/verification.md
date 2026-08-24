# Verification

## Green command and result

PASS on the exact working tree before review:

- Full suite and Local Green Gate: 190/190 tests PASS on macOS, including the real AF_UNIX broker path with no skip.
- `sddgov validate`: PASS.
- `sddgov ci verify`: PASS.
- All six packages present at that checkpoint (the five predecessor DEPs plus this R5 DEP): full and portable strict verification PASS.
- Wheel and sdist build: PASS.
- Fresh Python 3.11 wheel install: `pip check` PASS.
- Fresh Codex and Hermes installs: `doctor` PASS with 63 managed files each.
- Offline synthetic Muse pilot: PASS with `network_used=false` and `real_data_used=false`.

Package digests:

- wheel SHA-256: `b4cf8371a1eaae2a1c78e3ed5f41e6c1439b7165dec8d061477a0dab4e9f4908`
- sdist SHA-256: `85b33b2def55c3966112321627acffc022085c5687067cb03d39f554aa33e932`

Fresh install root: `/private/tmp/sdg-exp8-r5b-final-wheel-0lprRs` (local, disposable proof only).

## Before/after evidence

Before: Hosted run `31919258947` reached the Base-controlled Merge policy and rejected the v2-only gate with `rollback record is missing or incomplete`. After: candidate tests prove that one exact legacy v1 record is accepted only as non-executing migration data; wrappers, chaining, observational commands, alternate verification, duplicates, extra fields, and placeholders are blocked. Exact Base-verifier compatibility and Hosted proof remain gated on fresh independent review and the final audit receipt.

## Remaining limitations

One newly authorized Hosted Run is available after local and independent proof. No further rerun is authorized if that run fails.
