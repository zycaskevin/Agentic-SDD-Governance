# Reproduction

## Expected

`sddgov ci local-gate` serializes the complete Local Green critical section for
the current user. A competing invocation waits and does not execute contract
verification or repository commands until the first invocation exits.

## Actual

The implementation serializes commands only inside one invocation. Independent
processes can overlap, so repository-controlled gates may concurrently mutate
shared owner-private runtime roots. No cross-process lock exists around
`verify_guard` or command execution.

## Deterministic steps

At base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`, add the
test-only lock contract and run:

```text
PYTHONPATH=src python -m unittest discover \
  -s tests -p test_ci_guard_lock.py -v
```

Result: two errors. The process-contention test cannot find a Local Green
lock, and the orchestration-order test cannot patch the absent critical
section. See `shareable/artifacts/terminal--artifact-1.txt`.

## Environment and preconditions

- Python 3.11.15 on Linux.
- Synthetic temporary projects and lock directories only.
- No repository command was executed by the RED test.
- No network, credential, production, push, release, or shared installation.
