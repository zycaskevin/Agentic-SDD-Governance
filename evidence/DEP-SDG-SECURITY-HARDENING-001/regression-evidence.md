# Regression Evidence

## Regression test added or strengthened

- `tests/test_evidence_flow.py`: artifact mutation/deletion, complete raw/report coverage, Collector/media binding, unknown-extension/HAR disguise, traversal DEP ID, retained-dirfd Evidence-root creation, Collector input, Collector/Redactor/Verifier zones, attach verification snapshot, pre-write control swap rejection, default-output removal and custom-output restoration for write-boundary swaps, atomic manifest/report/summary parent replacement, hardlinks, symlinked source/destination/control files, duplicate collector label, and malformed Evidence contracts.
- `tests/test_autonomy.py`: category downgrade denial, same-UID/self-commit/root-Agent trust rejection, signed L2 import with byte-recalculated assumptions, signed L3 Runtime Context/scope/payload mismatch, secret-bearing parameters, fragmented real macOS Unix Broker protocol, extra-byte denial, fixed-platform and fail-closed parent checks, tampering, and expiry.
- `tests/test_merge_gate.py`: missing/malformed Base bootstrap state fails closed and Base revocation remains authoritative over stale external keys.
- `tests/test_repository_contract.py`: separate candidate/Base checkouts, `pull_request_target`, Base `PYTHONPATH`, full-SHA Action pins, hash-locked dependencies, and no candidate editable install.
- `tests/test_synthetic_muse_pilot.py`: fresh Hermes install plus offline synthetic text/single-image pilot.

## Related tests executed

- `python -m pytest -q` — 142/142 passed on macOS outside the restricted sandbox, including fragmented real Unix-socket protocol, extra-byte denial, same-directory control-file swap rollback, and all base/source/DEP/zone/output parent-replacement assertions.
- `python -m sddgov.cli validate .` — PASS.
- `python -m sddgov.cli ci verify .` — PASS.
- `python -m compileall -q src tests` — PASS.
- `python -m sddgov.cli pilot synthetic-muse` — PASS with `network_used=false` and `real_data_used=false`.
- A fresh temporary venv installed every trusted-verifier dependency from `requirements-governance.lock` with `--require-hashes` and ran repository validation. Exact-Head wheel/sdist and fresh-wheel Hermes smoke will be rerun after the reviewed implementation commit is sealed.

## Unaffected paths sampled

- Existing L0/L1 autonomous routing, Checkpoint behavior, artifact integrity, Reviewer bootstrap/signing, Merge digest, CI Cost Guard, install/doctor/uninstall, redaction rules, benchmark harness, adapters, and packaged-resource parity all passed in the same 142-test suite.
- The released experimental.6 wheel was used only as the Red baseline in disposable synthetic directories.
