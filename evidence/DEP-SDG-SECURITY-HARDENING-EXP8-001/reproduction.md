# Reproduction

## Expected

The trusted gate must fail closed when the caller's outer classification conflicts with nested authority, when workflow semantics exist only in comments, when a verified artifact or directory generation changes, when input is non-regular, or when a state/control write is incomplete.

## Actual

The experimental.7 baseline returned `CONTINUE` or `PASS` for several conflicting contracts and left filesystem/state residue after bounded injected failures.

## Deterministic steps

Run the targeted command recorded in `private/raw/terminal--experimental-8-red.txt`. The permanent regression tests exercise only temporary repositories and synthetic bytes. The baseline produces 15 failed checks.

## Environment and preconditions

Baseline `v0.2.0-experimental.7` at `f44cb5f4897f6c821f817fcf178581b43777163a`; branch `fix/security-hardening-exp8`; macOS; Python 3.14 test runner; no real data, credentials, Production authority, or hosted runner.
