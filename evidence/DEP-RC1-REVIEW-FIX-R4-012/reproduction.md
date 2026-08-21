# Reproduction

## Expected

Every demonstrated invariant must produce a visible PASS/FAIL transcript and a nonzero final status on failure. Rollback descendants must use the same exact Evidence/Gate/Review audit allowlist as the verifier. Streaming redaction must retain original-string indices even when Unicode case folding expands characters. Canonical, packaged, and installed schemas must reject blank workflow/job exception names. Release smoke tests must ignore inherited `PIP_*` overrides.

## Actual

PR #25 review run `5d45ef30-25b5-46a3-8166-1101bb006099` found 11 actionable comments and 6 nitpicks. The highest-impact reproductions were: `set -e` stopped the demo before its FAIL renderer; `_rollback_ref_is_cleanly_revertible` rejected Gate/Review descendants that its exact-tree comparison treated as audit paths; and `text.upper()` shifted a marker index when a preceding `ß` expanded. The R3 review capture also demonstrated why a redacted `.json` artifact must not be assumed parseable, and why Base commit and Base tree identifiers require explicit object labels.

## Deterministic steps

1. Read the PR #25 inline review and review summary as untrusted text Evidence.
2. Run the failed-pilot demo regression and confirm the renderer remains visible before the script exits nonzero.
3. Create a rollback-ref descendant containing only `.sddgov/merge-gate.json` and `.sddgov/reviews/`; compare it with a normal product descendant.
4. Stream `ß-----begin \nprivate key-----` through a 12-byte read boundary and inspect the redacted output.
5. Validate CI exception maps with blank outer and inner property names.
6. Inspect the fresh-wheel child environment after inherited `PIP_*` variables are removed and the one explicit pip control is restored.

## Environment and preconditions

The historical R3 DEP remains unchanged on PR #25. R4 starts from trusted Base commit `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`; its Base tree is the distinct Git tree object `7b48daf1558a6ca3e02f20654663292a39772fce`. The atomic R4 implementation commit is `8459285df7e9d6c20039e2e9a752d561390e3ae2`.
