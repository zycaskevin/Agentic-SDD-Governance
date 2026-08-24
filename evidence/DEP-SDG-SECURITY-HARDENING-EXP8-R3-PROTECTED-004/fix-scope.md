# Fix Scope

## Smallest sufficient change

Add `AGENTS.md`, `.agents/`, and `.agentic-sdd-governance/` to canonical and packaged protected-file policies and assert Base-derived coverage.

## Files or components in scope

- Canonical and packaged `policies/protected-files.yaml`
- Merge Gate and repository-contract regression tests
- Changelog and this DEP

## Explicit non-scope

No change to which party may sign a review, trust-store contents, or normal unprotected product-source policy.

## Blast radius

Low. The change adds review requirements to governance-bearing files and fails closed; it does not broaden execution authority.
