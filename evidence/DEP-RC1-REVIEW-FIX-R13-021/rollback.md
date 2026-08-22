# Rollback

rollback_version: 3.0
target: complete RC1 R13 implementation candidate
rollback_action: git_revert
rollback_ref: 096624a529dea88d091777c8012bbdba3346cdbe
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

# Revert if R13 weakens trusted-Base candidate isolation, allows a non-Evidence
# commit before reviewed Head, omits a hash-locked dependency set from the
# isolated full-test environment, or regresses any inherited RC1 hard gate.

## Reversible steps

# Revert the immutable single-parent product commit above. R6-R13 Evidence,
# the later R13 Merge Gate, and independent receipt remain audit descendants.

## Data compatibility

# No production data migration exists. The revert restores exact trusted Base
# code and schema behavior while retaining audit Evidence and gate history. No
# public RC1 package or real authority store was published or migrated.

## Post-rollback verification

    # Set ROLLBACK_ROOT to an isolated checkout, BASE_SHA to trusted Base,
    # ROLLBACK_TMP outside the checkout, and RELEASE_PYTHON to the external
    # hash-locked release environment used for package proof.
    # "$RELEASE_PYTHON" -m pip check
    # "$RELEASE_PYTHON" -c 'import build, twine'
    # cd "$ROLLBACK_ROOT"
    # WARNING: git revert changes the isolated checkout; verify all paths first.
    # git revert --no-commit 096624a529dea88d091777c8012bbdba3346cdbe
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
