# Fix Scope

## Smallest sufficient change

Create a fresh R13 product commit directly above the exact trusted Base, replay only Evidence audit commits before reviewed Head, defer the new Merge Gate until that Head is immutable, and install `requirements-release.lock` alongside `requirements-governance.lock` in the isolated workflow environment that runs every test. Add a structural regression assertion that both installs precede the suite.

## Files or components in scope

`.github/workflows/publish.yml`, `tests/test_repository_contract.py`, `work-packages/WP-RC1-READINESS-008.md`, Git candidate topology, and `evidence/DEP-RC1-REVIEW-FIX-R13-021/**`.

## Explicit non-scope

No trusted-Base verifier change; no force push or mutation of PR #34; no release-dependency promotion into runtime requirements; no receipt fabrication; no TestPyPI/PyPI/GitHub Release; no GitHub environment or ruleset change; no real key; no root Broker install; and no bypass, mock authority, or affected-path-only rollback proof.

## Blast radius

The fix changes the release workflow's isolated validation environment, a repository contract, Work Package authority metadata, and candidate history shape. It adds no runtime package dependency and performs no external publication. Risk is bounded by two hash-locked inputs, full tests, current and exact-Base verification, source validation, package/fresh-wheel proof, and a real single-commit revert drill.
