# Regression Evidence

## Regression test added or strengthened

`tests/test_ci_guard_lock.py` defines state-based cross-process contention and
one continuous `enter -> verify -> command -> exit` orchestration contract.

## Related tests executed

RED: two errors because `_local_gate_lock` does not exist.

Focused Green:

```text
PYTHONPATH=src python -m unittest discover \
  -s tests -p 'test_ci_guard*.py' -v
```

Result: `27` tests passed, including five new cross-process, fail-closed, and
exception-release contracts. Targeted changed-file Ruff safety rules
(`E4,E7,E9,F`), governance source validation,
managed-copy parity, and `git diff --check` passed. A first full suite reached
`233 passed, 1 skipped` with one managed-manifest failure; after updating the
exact managed document hash, that previously failing node passed.

The first orchestration-level Local Green attempt then exposed a nested-test
deadlock: the outer gate held the production lock while the unit-suite child
called `run_local_gate` to test command behavior. The unit tests now inject a
separate synthetic lock root for those two calls, while production callers and
the CLI retain the fixed current-user lock. Focused `27` tests and the same
targeted Ruff rules passed again after this correction. The production lock namespace was versioned before
integration so the unmerged experimental lock cannot affect the final gate.

The next exact-head gate exposed the only remaining nested path:
`test_exact_change_green_dep_rollback_and_review_pass` intentionally invokes
full merge verification from inside the unit-suite child. That test now injects
the same synthetic lock-root isolation as the two direct CI Guard unit tests.
The exact merge node passed, the `27` CI Guard tests passed, and the targeted
changed-file Ruff rules passed after this correction.

Exact committed-head Proof at
`196685c2680da9a84d4b5efd35dd66f20909f1b4`:

```text
PYTHONPATH=src python -m sddgov.cli ci local-gate .
```

Result: exit `0`; `237` repository tests completed: `236` passed and one
documented platform-dependent test was skipped, followed by successful
governance source validation.
The worktree remained clean. A share-safe derivative is retained as
`shareable/artifacts/terminal--exact-head-local-green.txt`; the full transcript
was reduced to this bounded derivative because the console output contains a
workstation-specific temporary checkout path.

## Unaffected paths sampled

Only synthetic temporary projects and lock roots are used. No consumer
repository command, external network, credential, or production path is
touched. Direct repository commands that bypass `sddgov` are intentionally not
serialized.
