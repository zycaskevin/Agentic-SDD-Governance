# Fix Scope

## Smallest sufficient change

Implement a bounded, exact legacy-v1 allowlist alongside declarative v2; enable v1 only for exact Base `f44cb5f4897f6c821f817fcf178581b43777163a` plus the selected migration rollback path, and retain v2 for future gates.

## Files or components in scope

- `src/sddgov/merge_gate.py`
- Merge Gate regression tests and Hard Gates documentation
- Current Merge Gate/receipt after fresh review
- This DEP and Changelog

## Explicit non-scope

No arbitrary shell execution, workflow trust-root change, hosted rerun bypass, Production operation, or stable release.

## Blast radius

Medium but bounded. Rollback parsing is security-critical; strict exact fields, duplicate rejection, immutable Git bytes, and fresh independent review are required.
