# Regression Evidence

## Regression test added or strengthened

`test_release_workflow_is_manual_isolated_and_attested` now extracts the exact `Validate the source contracts` step and requires both hash-locked install commands to occur before complete unittest discovery. `test_rc1_work_package_and_rollback_bind_current_proof` binds the Work Package to R13 as the authoritative package. The candidate topology itself is tested by rejecting any path outside `evidence/**` between atomic rollback ref and reviewed Head with the exact trusted Base verifier.

## Related tests executed

A fresh Python 3.12 environment installed both lock files with `--require-hashes`. The complete suite passed 357 tests with two explicit environmental skips. Doctor, source validation, CI Guard verification, and Local Gate passed. Package proof built and checked the wheel/sdist, assembled the ten-dependency locked offline bundle, and passed fresh-wheel Codex/Hermes Doctor/Validate plus the synthetic quick demo.

## Unaffected paths sampled

Autonomy classification and signed receipts, Broker framing/nonce controls, Evidence filesystem boundaries, streaming redaction, CI cost limits, protected-workflow permissions, descriptor-bound release assets, canonical/package/install parity, synthetic pilot, and historical portable DEP packages remain Green. The two skips are explicitly limited to sandbox Unix sockets and shallow-history Git behavior.
