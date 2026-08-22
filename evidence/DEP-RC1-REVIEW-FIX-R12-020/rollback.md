# Rollback

rollback_version: 3.0
target: complete RC1 R12 implementation candidate
rollback_action: git_revert
rollback_ref: f1e1e32217b54d429b80e2a9eeb97291a5b5d9d4
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R12 weakens complete Broker framing, pre-scan ledger capacity,
# trusted-approver authority, deployment/log retention, release interpreter
# determinism, historical proof accuracy, or exact-tree rollback.

## Reversible steps

# Revert the immutable single-parent implementation commit above. R6-R12
# Evidence, Gate, and review records remain audit-only descendants.

## Data compatibility

# No Production data migration exists. The revert restores trusted Base code
# and schema behavior while retaining immutable Evidence and gate history.
# The fixed trusted-approver path is a pre-release control-plane contract; no
# public release or real authority store was migrated in this candidate.

## Post-rollback verification

    # Set ROLLBACK_ROOT to an isolated checkout, BASE_SHA to the trusted exact
    # Base, ROLLBACK_TMP outside the checkout, and RELEASE_PYTHON to the external
    # release environment whose hash-locked install passed package proof before
    # entering the checkout.
    # "$RELEASE_PYTHON" -m pip check
    # "$RELEASE_PYTHON" -c 'import build, twine'
    # cd "$ROLLBACK_ROOT"
    # WARNING: git revert changes the isolated checkout; verify all three paths first.
    # git revert --no-commit f1e1e32217b54d429b80e2a9eeb97291a5b5d9d4
    # git diff --quiet "$BASE_SHA" -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**'
    # test -z "$(git ls-files --others --exclude-standard -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**')"
    # PYTHONPATH=src python3 -m sddgov.cli setup-agent . --agent codex --profile team-standard
    # PYTHONPATH=src python3 -m sddgov.cli doctor .
    # PYTHONPATH=src python3 -m sddgov.cli validate .
    # PYTHONPATH=src python3 -m unittest discover -s tests -v
    # "$RELEASE_PYTHON" -m build --no-isolation --outdir "$ROLLBACK_TMP/dist"
    # "$RELEASE_PYTHON" -m twine check "$ROLLBACK_TMP/dist"/*
    # test ! -e scripts/fresh_wheel_smoke.py
    # python3 -m venv --system-site-packages "$ROLLBACK_TMP/venv"
    # "$ROLLBACK_TMP/venv/bin/python" -m pip install --no-deps --force-reinstall "$ROLLBACK_TMP/dist/agentic_sdd_governance-0.2.0.dev8-py3-none-any.whl"
    # test "$("$ROLLBACK_TMP/venv/bin/python" -m sddgov.cli --version)" = "0.2.0-experimental.8"
    # git diff --quiet "$BASE_SHA" -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**'
    # test -z "$(git ls-files --others --exclude-standard -- . ':(exclude)evidence/**' ':(exclude).sddgov/merge-gate.json' ':(exclude).sddgov/reviews/**')"
    # Only after every command exits 0 is the rollback post-condition Green.
