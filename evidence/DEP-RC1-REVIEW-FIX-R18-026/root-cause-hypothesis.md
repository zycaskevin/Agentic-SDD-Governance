# Root Cause Hypothesis

## Hypothesis

The defects share an incomplete-boundary root cause: implementations validated only the final pathname/tree or common happy path while omitting alternate commit ancestry, descriptor-relative publication, byte ceilings, fragmented transport, and forward-only historical correction semantics.

## Supporting evidence

Independent reproduction showed an omitted add/remove side branch, full allocation before declared-size rejection, sentinel overwrite through both Pilot output paths, unmasked temporary paths, raw benchmark exception text, and unsupported approval/proof wording.

## Contradicting evidence

The R17 exact-tree rollback, dual-lock suite, package integrity, native Broker implementation, and two rejected CodeRabbit findings remained Green. Those results narrow the defect to the listed boundaries rather than the overall release design.

## Falsification test

The hypothesis would be false if a real add/remove side branch were enumerated by R17, if every low-level regular-file read already required a ceiling, if a Pilot symlink target survived R17, or if predecessor artifacts supported the disputed counts and ordering. Each falsification attempt contradicted R17.

## Conclusion

Confirmed. R18 addresses the common boundary directly: all reachable commits are enumerated, the reader has no unbounded default, public reports use retained directory descriptors and exclusive no-follow creation, path rules include temporary and quoted forms, and immutable history is corrected only by registered forward replacements.
