# Regression Evidence

## Regression test added or strengthened

- `tests/test_evidence_flow.py`: artifact mutation/deletion, complete raw/report coverage, unknown-extension bypass, HAR body blocking, traversal DEP ID, side-effect-free symlink rejection, hardlinks, symlinked source/destination/control files, duplicate collector label, and malformed Evidence contracts.
- `tests/test_autonomy.py`: category downgrade denial, same-UID/self-commit trust rejection, signed L2 import with byte-recalculated assumptions, signed L3 complete-context mismatch, secret-bearing parameters, external-broker fail-closed behavior, tampering, and expiry.
- `tests/test_merge_gate.py`: Base revocation remains authoritative over stale external bootstrap keys.
- `tests/test_repository_contract.py`: separate candidate/Base checkouts, `pull_request_target`, Base `PYTHONPATH`, and no candidate editable install.
- `tests/test_synthetic_muse_pilot.py`: fresh Hermes install plus offline synthetic text/single-image pilot.

## Related tests executed

- `python -m pytest tests/ -q` — 120/120 passed.
- `python -m sddgov.cli validate .` — PASS.
- `python -m sddgov.cli ci verify .` — PASS.
- `python -m compileall -q src tests` — PASS.
- `python -m sddgov.cli pilot synthetic-muse` — PASS with `network_used=false` and `real_data_used=false`.
- Isolated PEP 517 build produced the experimental.7 wheel and sdist. A fresh temporary venv installed the wheel, reported `0.2.0-experimental.7`, installed Hermes into a new project, passed `doctor`, and reran the synthetic Muse pilot with verdict `PASS`.

## Unaffected paths sampled

- Existing L0/L1 autonomous routing, Checkpoint behavior, artifact integrity, Reviewer bootstrap/signing, Merge digest, CI Cost Guard, install/doctor/uninstall, redaction rules, benchmark harness, adapters, and packaged-resource parity all passed in the same 120-test suite.
- The released experimental.6 wheel was used only as the Red baseline in disposable synthetic directories.
