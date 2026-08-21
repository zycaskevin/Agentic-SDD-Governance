# Rollback

rollback_version: 3.0
target: complete RC1 R7 implementation candidate
rollback_action: git_revert
rollback_ref: eb29619f4e9617b5f0e2a67569255e29af92d9ef
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R7 weakens subprocess status propagation, Evidence redaction,
# release-byte binding, Broker isolation, exact-tree rollback, or compatibility.

## Reversible steps

# Revert the immutable single-parent implementation commit above. R6/R7 Evidence,
# Gate, and review receipt commits remain audit-only descendants.

## Data compatibility

# No Production data migration is introduced. The revert restores Base code and
# managed governance; audit Evidence remains immutable and excluded from equality.

## Post-rollback verification

# Set ROLLBACK_ROOT to an isolated checkout, BASE_SHA to the trusted exact Base,
# and ROLLBACK_TMP outside the checkout. Do not use --force during reconciliation:
# the reverted managed tree is already current and its timestamp must stay exact.
# cd "$ROLLBACK_ROOT"
# git revert --no-commit eb29619f4e9617b5f0e2a67569255e29af92d9ef
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
# test "$("$ROLLBACK_TMP/venv/bin/python" -c "import importlib.metadata; print(importlib.metadata.version('agentic-sdd-governance'))")" = "0.2.0.dev8"
# git diff --quiet "$BASE_SHA" -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**'
# test -z "$(git ls-files --others --exclude-standard -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**')"
# The first assertion proves tracked equality with Base; the second rejects
# unexpected non-ignored, untracked rollback residue outside audit-only paths.
# Only after every command exits 0 is the rollback post-condition Green.
