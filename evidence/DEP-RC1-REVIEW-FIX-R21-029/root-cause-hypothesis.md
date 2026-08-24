# Root Cause Hypothesis

## Hypothesis

R20 validated pathnames and content at several individual points but did not retain one generation token across the complete write, close, claim, publication, parent-lease, and cleanup transaction. Redaction and release provenance likewise modeled common representations and success ordering without covering every supported serialized form or post-download state.

## Supporting evidence

The independent reviewer reproduced forged-but-valid control publication, forged attachment publication, replacement deletion at file and socket cleanup boundaries, output residue after close failure, outside-directory creation through a supplied-dirfd pathname, escaped UNC survival, and newline-split sensitive fields. Focused R21 regressions fail if identity/digest guards, outer transactions, or the new representation checks are removed.

## Contradicting evidence

R20 passed its complete local suite, package smoke, and native Broker happy paths. This contradicts a broad architectural failure and localizes the defect to missing transaction boundaries and adversarial representations.

## Falsification test

Run the new replacement and close tests with the descriptor guard or identity/digest claim removed; run streaming parity after removing cross-line detection; mutate an asset after one download. Each relevant regression must fail while unrelated suites remain Green.

## Conclusion

Confirmed. The smallest sufficient fix is generation-bound staging and cleanup, explicit pre/post-commit close semantics, complete streaming/path representations, and repeated inventory/control-plane validation.
