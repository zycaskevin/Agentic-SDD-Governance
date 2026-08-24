# Root Cause Hypothesis

## Hypothesis

Whole-text rules deliberately match quoted values across newlines, but the
streaming path applies those rules to one logical line at a time. It publishes
the opening line to staging before the closing quote is available, so the rule
never sees one complete match.

## Supporting evidence

The exact Red produces one whole-text password replacement and zero streaming
replacements. The streaming implementation retains private-key and split-field
state but has no state for a quoted value opened on one line and closed later.

## Contradicting evidence

Chunk-split matches that remain inside one logical line are already Green, and
newline-split field-name/delimiter sequences already fail closed. The defect is
limited to a value quote opened after a complete field prefix and closed on a
later logical line.

## Falsification test

Retain the candidate field without writing it, bound the retained characters,
scan escaped quotes, and apply the existing ordered stream rules only after the
closing quote. Compare output bytes and counts with `redact_text`; require
transactional failure at EOF, the bound, and invalid line escapes.

## Conclusion

Confirmed. The streaming state machine did not model incomplete quoted values.
