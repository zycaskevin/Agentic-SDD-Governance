# Rollback

rollback_version: 3.0
target: complete RC1 R9 implementation candidate
rollback_action: git_revert
rollback_ref: dfe51c5606a47641daeab3321651fcb949817d5b
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R9 weakens descriptor-bound release directories/files, bounded
# Evidence collection, owned-generation cleanup, CI fail-closed behavior,
# package proof, or exact-tree rollback.

## Reversible steps

# Revert the immutable single-parent implementation commit above. R6-R9
# Evidence, Gate, and review receipt commits remain audit-only descendants.

## Data compatibility

# No Production data migration exists. The revert restores trusted Base code
# and managed governance while retaining immutable Evidence and gate history.

## Post-rollback verification

# Set ROLLBACK_ROOT to an isolated checkout, BASE_SHA to the trusted exact Base,
# and ROLLBACK_TMP outside the checkout.
# cd "$ROLLBACK_ROOT"
# git revert --no-commit dfe51c5606a47641daeab3321651fcb949817d5b
# git diff --quiet "$BASE_SHA" -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**'
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
# If setup-agent requires --force during recovery, additionally prove that the
# only Base difference is manifest.json installed_at and that every other field
# equals the Base manifest. Only after every command exits 0 is rollback Green.
