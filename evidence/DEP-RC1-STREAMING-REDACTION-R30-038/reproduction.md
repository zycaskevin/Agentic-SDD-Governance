# Reproduction

## Expected

For a password or named secret whose single- or double-quoted value spans
logical lines, streaming redaction must publish no value bytes before it sees
and validates the closing quote. The final output and rule totals must match
`redact_text` for the same bounded input. EOF, an over-limit value, or a
backslash immediately escaping a physical line ending must fail closed.

## Actual

At exact R29 Gate `7c794b7100b4eae16a4c3986a7c65a334f840f04`,
`redact_text` replaced the synthetic multiline quoted password and reported
one password match. `redact_files` published both value fragments verbatim and
reported no match.

## Deterministic steps

1. Write a UTF-8 synthetic log whose quoted password value spans two logical
   lines.
2. Run `redact_text` on the complete string and record its output and totals.
3. Run `redact_files` with a two-byte stream chunk size on the same bytes.
4. Compare the published bytes and totals. Before R30 they differ and the
   synthetic value survives in the shareable output.
5. Repeat for both quote styles and for a named secret field.

## Environment and preconditions

Public PR #51, exact automated review of the R29 Gate, Python 3.12 on Linux.
Only synthetic strings were used. The locally processed Red transcript is
registered as `shareable/artifacts/terminal--r30-code-review-red.txt`.
