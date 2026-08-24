# Regression Evidence

## Regression test added or strengthened

`test_streaming_matches_whole_text_for_multiline_quoted_sensitive_fields`
covers password/passwd and API/client secret fields with both quote styles and
two-byte stream chunks. `test_incomplete_quoted_sensitive_fields_fail_transactionally`
covers EOF, the retained-character bound, invalid physical-line escapes, and
cleanup of both the current and a prior owned output.

## Related tests executed

The affected redaction suite passed 45 tests. With all predecessor Evidence
restored and the R30 DEP in Fix, the complete source suite executed 537 tests:
523 passed and 14 platform or sandbox cases were skipped. Repository validation
and CI Guard verification both passed. Local Green, package, rollback, and
installed-wheel results are recorded after the final product and Evidence
topology is frozen.

## Unaffected paths sampled

Existing private-key, split field-name/delimiter, path, provider credential,
source mutation, symlink, descriptor-close, later-writer preservation, and
multi-file transaction tests remain in the affected suite. The current
Owner-client digest was recomputed and remains equal to the signed request.
