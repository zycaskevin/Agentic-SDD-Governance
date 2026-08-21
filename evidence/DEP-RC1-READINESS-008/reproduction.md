# Reproduction

## Expected

- A regular text input larger than the trusted redaction limit is rejected before an unbounded read or regex scan.
- `sddgov broker doctor` emits a structured, non-consuming L3 readiness report without requiring a real approval receipt.
- A new user can run one deterministic offline demo and see allow, block, redaction, and evidence behavior.
- English onboarding, RC1 publishing preparation, recovery operations, and Monorepo performance evidence are executable and discoverable.

## Actual

- The existing 229-test suite passes, establishing a clean pre-change baseline.
- The 10 MiB + 1 byte oversized text reproduction timed out after five seconds with exit 124 instead of returning `input_exceeds_redaction_limit`.
- `sddgov broker doctor --json` is rejected by the argument parser with exit 3 because the command does not exist.
- No top-level demo, standalone publish workflow, Broker service assets, key ceremony guide, recovery guide, or Monorepo benchmark is present.

## Deterministic steps

1. Run `.venv/bin/python -m unittest discover -s tests -v`; observe 229 tests Green and two skipped.
2. Create a regular `.log` file containing 10 MiB + 1 byte of synthetic `x` characters.
3. Call `sddgov.redaction.redact_files` under `timeout 5s` and assert the report contains blocked reason `input_exceeds_redaction_limit`.
4. Observe timeout exit 124 instead of a bounded rejection.
5. Run `.venv/bin/sddgov broker doctor --json` and observe parser exit 3.
6. Inspect `README.md`, `.github/workflows/`, `docs/`, and benchmark/demo paths for the named deliverables.

## Environment and preconditions

- Baseline commit: `1a5a0b214eccc2b9edd076fd5e2f222c4a456725` (`v0.2.0-experimental.8`).
- Branch: `feat/rc1-readiness`.
- Runtime: Python 3.12.3, Git 2.43.0, Linux aarch64.
- Network is not used by the reproduction; all data is synthetic.
- Raw command output is retained only under `private/raw` and will not be attached.
