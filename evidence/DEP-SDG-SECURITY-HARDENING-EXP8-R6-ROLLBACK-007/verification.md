# Verification

## Green command and result

PASS on exact local Head `23d74e1`:

- Original hostile rollback selection: 4/4 PASS.
- Complete suite and Local Green Gate: 193/193 PASS, including the real macOS AF_UNIX broker test.
- `sddgov validate`: PASS.
- `sddgov ci verify`: PASS.
- All six predecessor DEPs: strict portable verification PASS after immutable-ref migration.
- Wheel and sdist build: PASS.
- Fresh Python 3.11 wheel install and `pip check`: PASS.
- Fresh Codex and Hermes `doctor`: PASS with 63 managed files each.
- Offline synthetic Muse pilot: PASS with `network_used=false` and `real_data_used=false`.

Package digests:

- wheel SHA-256: `274e94e87141907662e1539cbef6d7d24b37f65146ebeab43bde8eda76f606fc`
- sdist SHA-256: `49d1f144a05f4fd28a80dc1a976a0f67e29fb8a14a7565b05bcb589ed2b333b8`

Fresh install root: `/private/tmp/sdg-exp8-r6-final-wheel-jAuthw` (local disposable proof only).

## Before/after evidence

Before: v1 had no Base discriminator, `HEAD` and nonexistent refs passed, and standalone text was ignored. After: v1 requires the exact experimental.7 Base plus migration path; v1/v2 require a full existing SHA strictly inside Base-to-reviewed-Head; unknown standalone text, Base, out-of-range, abbreviated, symbolic, and nonexistent refs fail closed.

## Remaining limitations

Raw evidence stays local. Fresh clones can independently verify portable DEP evidence but cannot claim full-local raw proof. A new independent review is still required; no Hosted rerun is authorized by this fix.
