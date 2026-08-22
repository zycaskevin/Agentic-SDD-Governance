# Root Cause Hypothesis

## Hypothesis

The sanitizer only recognized `prefix/` followed by non-whitespace, so it did
not match a bare prefix and stopped at the first path space. Separately, CLI
report output stayed outside the descriptor-bound release filesystem layer and
the bundle exception allowlist omitted the decompressor's native error. The
governance mismatch resulted from copying predecessor L2 metadata forward even
though the authoritative Work Package had no unresolved product decision.

## Supporting evidence

The exact R16 regular expression requires a path separator and uses `[^\s\n]*`.
Both failures follow directly. Both CLI mains use `mkdir`/`write_text`, while
`release_files.py` already provides no-follow descriptor primitives. The
Reviewer reproduced the symlink overwrite and public path residual. The WP
Risk line is L1, R16 summary/Gate are L2, and `.sddgov/decisions.json` is empty.

## Contradicting evidence

Existing temporary paths without spaces were fully masked, descriptor-bound
release inputs and bundle outputs already rejected symlinks, and all 381 R16
tests were Green. These facts narrow the fault to the public error/report edge
and metadata provenance rather than the underlying bundle inventory or Broker.

## Falsification test

The hypothesis is false if a boundary-aware sanitizer still leaks the bare
prefix or space-containing suffix; a descriptor-bound `O_EXCL|O_NOFOLLOW`
writer overwrites a symlink target; `zlib.error` escapes the CLI JSON handler;
or an L1 R17 DEP/Gate still requires a nonexistent owner decision package.

## Conclusion

Confirmed. R17 centralizes boundary-aware local-path masking, uses a secure
descriptor walk plus exclusive report creation in both release CLIs, catches
compressed-stream errors, and binds the current Work Package/DEP/Gate to L1.
Historical Evidence is retained byte-for-byte as predecessor audit.
