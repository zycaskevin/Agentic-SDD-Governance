# Regression Evidence

## Regression test added or strengthened

- `tests/test_evidence_flow.py`: artifact mutation/deletion, traversal DEP ID, symlinked source/destination/control files, duplicate collector label, unregistered and malformed Evidence contracts.
- `tests/test_autonomy.py`: category downgrade denial, signed L2 import/reuse, stale assumptions, signed L3 complete-payload mismatch, secret-bearing parameters, replay, tampering, expiry, and concurrent one-use consumption.
- `tests/test_repository_contract.py`: separate candidate/Base checkouts, `pull_request_target`, Base `PYTHONPATH`, and no candidate editable install.
- `tests/test_synthetic_muse_pilot.py`: fresh Hermes install plus offline synthetic text/single-image pilot.

## Related tests executed

- `python -m pytest tests/ -q` — 113/113 passed.
- `python -m sddgov.cli validate .` — PASS.
- `python -m sddgov.cli ci verify .` — PASS.
- `python -m compileall -q src tests` — PASS.
- `python -m sddgov.cli pilot synthetic-muse` — PASS with `network_used=false` and `real_data_used=false`.
- Isolated PEP 517 build produced the experimental.7 wheel and sdist. A fresh temporary venv installed the wheel, reported `0.2.0-experimental.7`, installed Hermes into a new project, passed `doctor`, and reran the synthetic Muse pilot with verdict `PASS`.

## Unaffected paths sampled

- Existing L0/L1 autonomous routing, Checkpoint behavior, artifact integrity, Reviewer bootstrap/signing, Merge digest, CI Cost Guard, install/doctor/uninstall, redaction rules, benchmark harness, adapters, and packaged-resource parity all passed in the same 113-test suite.
- The released experimental.6 wheel was used only as the Red baseline in disposable synthetic directories.
