# Fix Scope

## Smallest sufficient change

Close the verified R12 review boundaries with EOF-bound Broker framing, pre-scan capacity checks and early telemetry, fixed trusted-approver authority, guarded platform downloads, exact macOS service installation/log retention, pinned protected-job Python, runtime/release dependency separation, public resource access, exact CI exemption semantics, portable tests, and precise historical proof. Preserve all product, test, documentation, and Work Package changes in one atomic commit directly above Base.

## Files or components in scope

`src/sddgov/broker.py`, `src/sddgov/autonomy.py`, `src/sddgov/trust.py`, `src/sddgov/installer.py`, `src/sddgov/cli.py`, `src/sddgov/ci_guard.py`, Broker service assets and packaged mirrors, macOS newsyslog configuration, publish workflow, runtime and release locks, English and Traditional Chinese install/runbook documentation, R6/R10 historical Evidence corrections, Work Package sequencing, and focused unit/repository tests.

## Explicit non-scope

No TestPyPI/PyPI/GitHub Release publication; no GitHub environment or ruleset mutation; no real Owner key; no root Broker installation; no WSL2/macOS privileged rehearsal; no unvalidated systemd syscall allow list; no mock Broker, risk reclassification, rollback bypass, affected-path-only proof, force push, old review-thread reply/resolution, or fabricated independent review receipt.

## Blast radius

The changes touch L2/L3 authority selection, L3 availability, nonce replay protection, service deployment, local/offline installation, CI publication gates, packaging dependencies, and public audit claims. Risk is bounded by fail-closed regression tests, exact canonical/package/install parity, source-before-build validation, fresh-wheel isolation, unchanged 64 MiB hard capacity, seven compressed 1 MiB macOS log rotations, and a real full-tree Base rollback rehearsal.
