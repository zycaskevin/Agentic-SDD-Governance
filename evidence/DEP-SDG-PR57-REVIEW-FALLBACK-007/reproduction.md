# Reproduction

## Expected

An automated reviewer status must represent an actual review; a skipped or unavailable provider must not block release readiness forever.

## Actual

The provider reported success while explicitly skipping review, and repeated CLI attempts produced no usable final review.

## Deterministic steps

Validate the executable product contract, simulate the fallback fields, run full Local Green, and perform the exact v4 rollback drill.

## Environment and preconditions

The Owner approved this bounded product rule in plain language on 2026-08-29; no terminal or cryptographic ceremony was used.
