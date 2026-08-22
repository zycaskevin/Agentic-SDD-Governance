# Fix Scope

## Smallest sufficient change

Extend `_draft_condition_is_safe()` with a flat-conjunction recognizer. It must
first preserve the two exact legacy forms, then reject disjunctions and accept a
conjunction only when every term matches a simple GitHub-context comparison
grammar and one complete term is exactly the Draft-false predicate.

## Files or components in scope

- `src/sddgov/ci_guard.py`
- `tests/test_ci_guard.py`
- Root, managed, packaged, and Skill copies of CI Cost Guard documentation
- Version/release metadata required for an isolated experimental.9 wheel
- Work Package and `DEP-CI-STRICTER-DRAFT-GUARDS-016`

## Explicit non-scope

No arbitrary GitHub expression evaluator, AST dependency, operator precedence,
function calls, parentheses, nested interpolation, CI policy weakening,
VoiceKey product source, billing policy, runner execution, or release action.

## Blast radius

Only jobs in workflows with exactly one PR event family and an enabled Draft
skip control can use the new recognition path. Existing exact guards are byte-
compatible. Unsupported expressions continue to fail closed. Downstream
VoiceKey gains validation of its narrower PR #48 job condition but no runtime
authority from this code change alone.
