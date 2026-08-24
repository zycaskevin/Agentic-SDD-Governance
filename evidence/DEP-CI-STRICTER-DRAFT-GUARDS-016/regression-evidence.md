# Regression Evidence

## Regression test added or strengthened

`tests/test_ci_guard.py` now proves the exact VoiceKey PR #48 conjunction and a
minimal wrapped conjunction are accepted. A separate positive test binds the
same rule to `pull_request_target`.

## Related tests executed

`PYTHONPATH=src python3 -m unittest tests.test_ci_guard -v`: 22 tests passed.
The existing legacy, always-true bypass, malformed YAML, permission, runner,
concurrency, timeout, symlink, hardlink, and local-gate checks remain Green.

`PYTHONPATH=src python3 -m unittest discover -s tests -v`: 232 tests passed;
the one sandbox-only AF_UNIX test was separately rerun outside the workspace
sandbox and passed. Validation, CI verification, Local Green, reproducible
wheel comparison, and downstream installed-wheel verification also passed.

## Unaffected paths sampled

The positive path does not modify the parsed workflow, contract, runner labels,
permissions, events, or commands. Nine new hostile expressions remain rejected,
including missing and mismatched PR event bindings. The downstream check uses
the exact VoiceKey job-level condition that motivated Issue #44.
