# Regression Evidence

## Regression test added or strengthened

Added adversarial tests for unknown and dangerous downgrade classification, tampered/untrusted/expired/replayed signed L3 receipts, concurrent atomic consumption, protected-file review enforcement, raw Evidence rejection, packaged parity, and CI Merge invocation.

## Related tests executed

`PYTHONPATH=src python3 -m unittest discover -s tests -v`: 68 tests passed after the Fix. Final exact-head count is recorded in `verification.md` after review receipts are bound.

## Unaffected paths sampled

Routine L0/L1 categories, Checkpoint, Decision reuse, Production eight-guard evaluation, artifact integrity, DEP, Redaction, installer, Hermes/Codex adapters, Benchmark, CI Cost Guard, and repository validation.
