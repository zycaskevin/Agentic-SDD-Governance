# Verification

## Green command and result

`PYTHONPATH=src python3 -m unittest tests.test_ci_guard -v` returned `0`; all 22
Cost Guard tests passed.

## Full verification matrix

- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 232 passed; the
  sandbox-only AF_UNIX protocol test skipped because the workspace sandbox
  denies socket creation.
- The skipped AF_UNIX protocol test was rerun outside that sandbox and passed.
- `PYTHONPATH=src python3 -m sddgov.cli validate .`: PASS.
- `PYTHONPATH=src python3 -m sddgov.cli ci verify .`: PASS.
- `PYTHONPATH=src python3 -m sddgov.cli ci local-gate .`: PASS, including the
  full suite and validation.
- Doctor after managed-file regeneration: 66 managed files, zero errors and
  zero warnings.

## Artifact and downstream proof

Two committed-source wheel builds produced the identical SHA-256
`51fadf84492fc42de46a0734e7bab3f541ea727cdaf3ebe199132e0922d9ff5d` for
`agentic_sdd_governance-0.2.0.dev9-py3-none-any.whl`. An isolated consumer
environment reported `0.2.0-experimental.9` and its installed `sddgov ci verify`
accepted the exact VoiceKey PR #48 conjunction.

## Before/after evidence

Before: the safe four-atom PR #48 conjunction failed while hostile cases were
rejected. After: both PR-family positive forms pass and all legacy/hostile cases
retain their prior result. Shareable artifacts 1-3 contain the content-free
Red context and targeted Green receipt.

## Remaining limitations

The grammar intentionally does not evaluate general GitHub expressions. It
accepts only exact legacy guards or flat conjunctions of simple comparisons
with matching event-name and Draft-false atoms. Independent review, hosted CI,
merge authorization, and public release remain separate gates.
