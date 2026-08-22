# Reproduction

## Expected

The trusted Gate enumerates every commit reachable from the current Head but not the reviewed Head; every untrusted DEP read is bounded; caller-selected reports cannot follow symlinks; shareable text masks host temporary and space-containing paths; and public benchmark errors, incident runbooks, documentation, and historical proof claims preserve their declared security boundaries.

## Actual

R17 omitted non-descendant side-branch commits from its audit scan, allowed several DEP reads without a byte ceiling, followed Pilot output symlinks, leaked temporary paths through the core redactor and raw benchmark exceptions, and lacked explicit L3 approval language. The independent reviewer also found four historical proof-claim discrepancies that require forward-only corrections.

## Deterministic steps

1. Construct a side branch that adds and then removes a product file before merging it after reviewed Head; the R17 helper returns true because `--ancestry-path` omits both side commits.
2. Invoke the verifier with an artifact larger than a patched test ceiling; R17 reads it before the declared-size comparison.
3. Point each Pilot output path at a sentinel symlink; R17 overwrites the sentinel.
4. Redact quoted temporary paths containing spaces and inspect a failing Monorepo benchmark report; R17 leaves host-specific text in shareable output.
5. Compare the R6, R12, R13, and R14 artifacts with their prose claims and ordering.

## Environment and preconditions

Trusted Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`; R17 reviewed Head `5bdc016df9bff53cd8406d98f4b6fbd6fd5efd09`; R17 Gate Head `1f280183882ec397982b302de25aa66c99cfbcf6`; Linux Python 3.12 isolated dual-lock environment; independent review of PR #39.
