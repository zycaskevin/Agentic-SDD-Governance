# Rollback

rollback_version: 3.0
target: complete RC1 R11 implementation candidate
rollback_action: git_revert
rollback_ref: c49c46e2d07a328636461bda8106b65326f25507
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R11 weakens Broker ownership/group/capacity behavior, exact CI
# exceptions, release/Evidence transactionality, platform/proof accuracy, or
# exact-tree rollback.

## Reversible steps

# Revert the immutable single-parent implementation commit above. R6-R11
# Evidence, Gate, and review records remain audit-only descendants.

## Data compatibility

# No Production data migration exists. The revert restores trusted Base code
# and schema behavior while retaining immutable Evidence and gate history.
# This R11 bootstrap DEP uses manifest schema 1.0 legacy JSON media labels so
# the trusted Base verifier can consume every retained audit descendant.

## Post-rollback verification

# Set ROLLBACK_ROOT to an isolated checkout, BASE_SHA to the trusted exact Base,
# and ROLLBACK_TMP outside the checkout.
# cd "$ROLLBACK_ROOT"
# git revert --no-commit c49c46e2d07a328636461bda8106b65326f25507
# git diff --quiet "$BASE_SHA" -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**'
# test -z "$(git ls-files --others --exclude-standard -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**')"
# PYTHONPATH=src python3 -m sddgov.cli setup-agent . --agent codex --profile team-standard
# PYTHONPATH=src python3 -m sddgov.cli doctor .
# PYTHONPATH=src python3 -m sddgov.cli validate .
# PYTHONPATH=src python3 -m unittest discover -s tests -v
# python3 -m build --no-isolation --outdir "$ROLLBACK_TMP/dist"
# python3 -m twine check "$ROLLBACK_TMP/dist"/*
# test ! -e scripts/fresh_wheel_smoke.py
# python3 -m venv --system-site-packages "$ROLLBACK_TMP/venv"
# "$ROLLBACK_TMP/venv/bin/python" -m pip install --no-deps --force-reinstall "$ROLLBACK_TMP/dist/agentic_sdd_governance-0.2.0.dev8-py3-none-any.whl"
# test "$("$ROLLBACK_TMP/venv/bin/python" -m sddgov.cli --version)" = "0.2.0-experimental.8"
# git diff --quiet "$BASE_SHA" -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**'
# test -z "$(git ls-files --others --exclude-standard -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**')"
# Only after every command exits 0 is the rollback post-condition Green.
