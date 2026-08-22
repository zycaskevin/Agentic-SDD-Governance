# Root Cause Hypothesis

## Hypothesis

`_draft_condition_is_safe()` equates safety with exact textual equality to two
legacy cross-event guards. It has no bounded representation for a conjunction
whose execution set is strictly smaller and independently requires the same
non-Draft predicate.

## Supporting evidence

- Source inspection shows a two-element `accepted` set after whitespace removal.
- The Red positive test uses four `&&` comparisons including the exact Draft-false
  atom and is rejected.
- Replacing it with the broader legacy string makes the verifier pass, while an
  independent VoiceKey review proves that broader string allocates the
  self-hosted runner outside the authorized PR/event boundary.

## Contradicting evidence

The exact legacy strings still pass, and the existing always-true `||` attack
plus seven new hostile grammar cases are rejected. This contradicts a general
YAML parsing failure and localizes the defect to safe-condition recognition.

## Falsification test

Implement a deliberately small grammar for flat comparison conjunctions. The
hypothesis is false if the exact VoiceKey conjunction remains rejected, or if
any `||`, parentheses, function, negated/wrong Draft comparison, incomplete
atom, or reversed Draft atom becomes accepted.

## Conclusion

Confirmed before implementation. Preserve exact legacy matching and add only a
fail-closed conjunction path that requires an independent top-level
`github.event.pull_request.draft == false` comparison.
