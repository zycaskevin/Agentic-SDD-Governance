# Fix Scope

## Smallest sufficient change

Repair only the public release-error/report publication boundary and current
R17 governance provenance. Reuse the existing release filesystem invariants;
do not weaken or redesign the bundle, Broker, approval, or merge verifier.

## Files or components in scope

- Shared local-path masking and descriptor-bound report creation in
  `scripts/release_files.py`.
- Both bundle preparation and fresh-wheel CLI report paths.
- Regression tests for bare/space-containing paths, prefix siblings, symlink
  preservation, nested safe parents, and compressed-stream errors.
- WP R17 provenance, an authoritative L1 DEP, and an L1 Gate.

## Explicit non-scope

No public package publication, root service installation, production data,
Owner key/decision generation, reviewer key handling, runtime Broker change,
policy relaxation, historical R6-R16 Evidence rewrite, or benchmark claim.

## Blast radius

Release CLI failure reporting and its filesystem helper surface, plus current
governance metadata. Successful bundle contents, hashes, package runtime APIs,
L3 protocol/state, and product data schemas are unchanged.
