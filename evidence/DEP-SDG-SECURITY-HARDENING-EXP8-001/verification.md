# Verification

## Green command and result

`PYTHONPATH=src /private/tmp/sdg-exp8-test-venv/bin/python -m pytest -q -ra` passes all 166 tests outside the restricted execution sandbox, including the real AF_UNIX L3 approval-broker protocol test. The lock was resolved for Python 3.12; a fresh Python 3.11 environment installs it with `--require-hashes`, resolves `cryptography==50.0.0` plus the required compatibility dependency, and passes the same 166 tests.

## Before/after evidence

Before: 15 new defensive checks failed on experimental.7. After: the same checks and complete suite pass; `sddgov validate .`, semantic `sddgov ci verify .`, and `sddgov ci local-gate .` pass. The exact experimental.8 wheel and sdist contain no absolute/traversal paths or symlinks, fresh Codex/Hermes setup plus `doctor` pass with 63 managed files, `pip check` reports no broken requirements, and the offline synthetic Muse pilot passes with `network_used=false` and `real_data_used=false`.

## Remaining limitations

The restricted sandbox still skips one real Unix-socket test, so the unrestricted 166/166 result is the authoritative local proof. Production, real Muse data, credentials, hosted CI, Merge, independent approval, and Release are not claimed by this package; fresh independent review remains mandatory before Merge and this unreleased candidate is not a production gate.
