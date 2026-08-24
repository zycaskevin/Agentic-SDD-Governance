# Rollback

rollback_version: 3.0
target: complete R6 review-hardening implementation candidate
rollback_action: git_revert
rollback_ref: 4e45b924751d9bf4960972fad965b308a2cb8acb
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R6 weakens release-byte binding, Evidence integrity, Broker isolation,
# exact-tree rollback, or installed-governance compatibility.

## Reversible steps

# Revert the immutable single-parent implementation commit above; later Evidence,
# Gate, and review receipt commits remain audit-only descendants.

## Data compatibility

# No Production data migration is introduced. Reconciliation restores the Base
# managed resources and CI schema; R6 Evidence remains an immutable audit record.

## Post-rollback verification

# Set ROLLBACK_ROOT to the isolated checkout, BASE_SHA to the trusted exact Base,
# and ROLLBACK_TMP to a new directory outside the checkout. Every command below
# must succeed in order; validation and tests complete before packaging.
# cd "$ROLLBACK_ROOT"
# git revert --no-commit 4e45b924751d9bf4960972fad965b308a2cb8acb
# PYTHONPATH=src python3 -m sddgov.cli setup-agent . --agent codex --profile team-standard --force
# PYTHONPATH=src python3 -m sddgov.cli doctor .
# PYTHONPATH=src python3 -m sddgov.cli validate .
# PYTHONPATH=src python3 -m unittest discover -s tests -v
# python3 -m build --no-isolation --outdir "$ROLLBACK_TMP/dist"
# python3 -m twine check "$ROLLBACK_TMP/dist"/*
# test ! -e scripts/fresh_wheel_smoke.py
# python3 -m venv --system-site-packages "$ROLLBACK_TMP/venv"
# "$ROLLBACK_TMP/venv/bin/python" -m pip install --no-deps --force-reinstall "$ROLLBACK_TMP/dist/agentic_sdd_governance-0.2.0.dev8-py3-none-any.whl"
# test "$("$ROLLBACK_TMP/venv/bin/python" -m sddgov.cli --version)" = "0.2.0.dev8"
# git diff --quiet "$BASE_SHA" -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**'
# Only after all commands exit 0 is the rollback post-condition Green.
