# Reproduction

## Expected

Cleanup preserves later writers; reports reject symlink leaves/parents;
supported platform paths normalize or redact safely; health requires exactly
`READY\n` plus EOF; withdrawals cover only registered artifacts; native wheel
smoke works on Linux/macOS; automated review covers product/current Evidence.

## Actual

R18 deleted a replacement, overwrote a benchmark symlink target, exposed
supported Darwin/WSL paths, accepted health before delayed extra bytes,
suppressed an unregistered `files[999]` error, rejected Darwin system aliases,
and was skipped by CodeRabbit at 312 selected files.

## Deterministic steps

Run R19 filesystem, benchmark, redaction, release, repository-contract, and
real AF_UNIX regressions; build the wheel, assemble the locked offline bundle,
run checkout-free fresh-wheel smoke, and compare atomic rollback to exact Base.

## Environment and preconditions

Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`; R19 atomic product
`d7f40bcd1929aaab5c2327e69b7ffd2bc58a0ae0`; Python 3.12; Linux aarch64
local proof. Hosted Ubuntu/macOS-15 remains required before signature.
