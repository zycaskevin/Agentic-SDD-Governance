# Root Cause Hypothesis

## Hypothesis

The security claims fail because trust decisions are made from candidate-controlled code or caller-controlled metadata, while Evidence verification validates document shape and declared hashes without independently re-opening every referenced filesystem object.

## Supporting evidence

- The workflow checks out and installs the PR head before invoking the Merge verifier.
- Strict DEP verification does not iterate manifest rows to validate path, file type, size, digest, uniqueness, and report association.
- DEP creation accepts an unsanitized caller-provided ID; collection and redaction permit existing per-file links or names.
- Generic L0/L1 fallback runs after product/high-risk categories, direct decision recording writes `approved`, and L2 reuse defaults missing freshness inputs to safe values.
- L3 signatures cover an operation identifier and prose scope but not the canonical target, parameters, category, and effects object used at execution time.

## Contradicting evidence

The existing implementation already protects trusted reviewer and L3 public-key sources, rejects unknown categories, consumes L3 receipts once, detects protected-path changes, and blocks linked top-level Evidence zones. These controls show the failure is bounded to verifier provenance, per-artifact integrity, category minimums, L2 authority provenance, and complete L3 payload binding rather than a total absence of fail-closed behavior.

## Falsification test

Load the verifier from an immutable base checkout; add adversarial path/link/digest/authority tests; then require exact portable artifact recalculation, local raw recalculation, owner-signed L2 envelopes with explicit reuse inputs, and an L3 payload digest. The hypothesis is falsified if any original adversarial test still passes or normal signed/routine paths can no longer complete.

## Conclusion

Confirmed. Independent synthetic reproduction and source inspection agree on the same missing trust bindings.
