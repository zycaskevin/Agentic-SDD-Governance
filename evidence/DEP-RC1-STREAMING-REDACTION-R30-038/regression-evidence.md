# Regression Evidence

## Regression test added or strengthened

`test_streaming_matches_whole_text_for_multiline_quoted_sensitive_fields`
covers password/passwd and API/client secret fields with both quote styles and
two-byte stream chunks. `test_incomplete_quoted_sensitive_fields_fail_transactionally`
covers EOF, the retained-character bound, invalid physical-line escapes, and
cleanup of both the current and a prior owned output.

## Related tests executed

The affected redaction suite passed 45 tests. With all predecessor Evidence
restored and the R30 DEP in Green, the complete source suite executed 537
tests: 523 passed and 14 platform or sandbox cases were skipped. Repository
validation and CI Guard verification both passed. Candidate build, Twine,
offline bundle, and fresh installed-wheel smoke passed. The installed-wheel
smoke imported no source checkout, validated both managed Agent adapters,
passed the synthetic demo, and passed the native Linux Broker checks. An
actual revert restored the exact trusted-Base non-audit tree; Base setup,
Doctor, validation, build, Twine, and 237-test suite passed with one expected
sandbox skip.

## Unaffected paths sampled

Existing private-key, split field-name/delimiter, path, provider credential,
source mutation, symlink, descriptor-close, later-writer preservation, and
multi-file transaction tests remain in the affected suite. The current
Owner-client digest was recomputed and remains equal to the signed request.
