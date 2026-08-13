# Regression Evidence

## Regression test added or strengthened

Added adversarial tests for unknown and dangerous downgrade classification, strict sensitive-effect keys, duplicate trust identities, tampered/untrusted/expired/replayed signed L3 receipts, concurrent atomic consumption, trusted-base protected-file review enforcement, metadata tampering, deleted raw Evidence history, structured Rollback, packaged parity, and exact-head CI Merge invocation.

## Related tests executed

`PYTHONPATH=src python3 -m unittest discover -s tests -v`: 75 tests passed after the CodeRabbit review fixes. Final exact-head Local Green is recorded in `verification.md` after the follow-up commit.

## Unaffected paths sampled

Routine L0/L1 categories, Checkpoint, Decision reuse, Production eight-guard evaluation, artifact integrity, DEP, Redaction, installer, Hermes/Codex adapters, Benchmark, CI Cost Guard, and repository validation.
