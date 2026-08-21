# Reproduction

## Expected

Every release artifact and installed byte is bound to the reviewed version and
lock; Broker and redaction operations remain bounded and generation-safe; CLI,
schema, pilot, and documentation contracts fail loudly on incomplete inputs.

## Actual

R5 accepted multiple unbound or mutable inputs. The exact CodeRabbit review on
PR #27 supplied the source findings, and focused Red tests failed or errored at
the release, Broker, redaction, installer, CI, README, and pilot boundaries.

## Deterministic steps

From R5 implementation commit `05e53253d4e2e4b756e0b1edf07ea4d691124d76`,
run:

```bash
PYTHONPATH=src .venv/bin/python -m unittest -v \
  tests.test_release_bundle tests.test_broker tests.test_installer \
  tests.test_redaction tests.test_ci_guard tests.test_repository_contract \
  tests.test_synthetic_muse_pilot tests.test_monorepo_benchmark
```

The command exited 1 after 91 tests. The complete output is attached as
`terminal--r6-red-tests.txt`; review node and thread URLs are attached as
`git--r6-review-bindings.txt`.

## Environment and preconditions

Linux aarch64, Python 3.12, clean R6 branch forked from trusted Base
`1a5a0b214eccc2b9edd076fd5e2f222c4a456725` with R5 cherry-picked as one
single-parent implementation commit. No Production, customer, payment, key,
root-service, registry publication, or hosted release action was used.

The CodeRabbit allegation that the R5 gate digest was stale was not reproduced:
the gate records the implementation-plus-Evidence reviewed Head and permits only
documented Gate/review audit descendants; raw unstripped Git bytes are not the
canonical digest input. Missing independent signed review remains a real Merge
blocker and is not bypassed here.
