# Reproduction

## Expected

`verify_guard()` accepts an opt-in PR job only when the condition is a flat,
fail-closed conjunction containing the independent atom
`github.event.pull_request.draft == false`.

## Actual

The experimental.8 implementation accepts only two exact legacy strings. The
strict VoiceKey PR #48 condition is rejected even though its execution set is a
proper subset of non-Draft PR runs.

## Deterministic steps

From exact base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`, add the two
targeted tests in `tests/test_ci_guard.py`, then run:

```text
PYTHONPATH=src python3 -m unittest tests.test_ci_guard.CICostGuardTests.test_stricter_flat_conjunction_may_require_non_draft_pr tests.test_ci_guard.CICostGuardTests.test_stricter_draft_guard_grammar_fails_closed -v
```

The positive stricter-conjunction case fails; all hostile grammar cases remain
rejected.

## Environment and preconditions

Clean branch `codex/fix-stricter-draft-guards` from tag
`v0.2.0-experimental.8`; Ubuntu 24.04 aarch64; Python 3.12.3. The downstream
reproducer is the local, unpublished VoiceKey workflow commit for Issue #43 / PR
#48. No runner, provider, production data, or repository-sensitive value is
required.
