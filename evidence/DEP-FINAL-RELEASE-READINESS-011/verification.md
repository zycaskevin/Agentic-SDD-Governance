# Verification

## Green command and result

PASS: 216 tests; `sddgov validate`; `sddgov ci verify`; Local Green; every tracked Proof DEP portable strict; `pip-audit` reports no known vulnerabilities; wheel and sdist build; fresh-wheel Codex/Hermes setup and Doctor (66 files each); `pip check`; offline synthetic Muse pilot.

## Before/after evidence

Before: exit-code false success, repeated UAT, unsigned local completion, first-consumer dead end, three nonportable historical Proof DEPs, and CI TypeError. After: each case has a deterministic fail-closed or autonomous-continuation regression and the complete matrix is Green.

## Remaining limitations

The Unix socket positive test is skipped only in this execution sandbox. GitHub security settings, signed/attested tag provenance, final independent Review, one hosted verification, and downloaded Release-asset smoke remain separate pre-release gates.
