# Regression Evidence

## Regression test added or strengthened

Added adversarial tests for unknown, omitted, and dangerous downgrade classification; strict sensitive-effect keys; owner-only external trust files; immutable Approver Base refs; duplicate trust identities; tampered/untrusted/expired/replayed signed L3 receipts; concurrent atomic consumption; base-preferred protected-file Review enforcement; independent signer Base selection; metadata tampering; NUL-safe changed paths; deleted raw Evidence history; structured Rollback; packaged parity; and exact-head CI Merge invocation.

## Related tests executed

`PYTHONPATH=src python3 -m unittest discover -s tests -v`: 100 tests passed at implementation commit `83cc5a4abdb1ca33efd0888bb84b845f92ed7347` after the final trust-boundary audit. Exact-head Local Green is recorded in `verification.md` after the gate and receipt audit commits.

## Unaffected paths sampled

Routine L0/L1 categories, Checkpoint, Decision reuse, Production eight-guard evaluation, artifact integrity, DEP, Redaction, installer, Hermes/Codex adapters, Benchmark, CI Cost Guard, and repository validation.
