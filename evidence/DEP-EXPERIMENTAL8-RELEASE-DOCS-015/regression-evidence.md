# Regression Evidence

## Regression test added or strengthened

Added a deterministic release-doc assertion to this Work Package: the five current public documents must contain no experimental.6 install command and no experimental.8 `unreleased` or `in progress` marker. Historical prior-release records remain allowed.

## Related tests executed

- Exact version-reference search: PASS, zero matches.
- Pytest: 228 PASS, 1 sandbox-only AF_UNIX skip; no failures.
- `sddgov validate .`: PASS.
- `sddgov ci verify .`: PASS.
- `sddgov ci local-gate .`: PASS, 229 unittest cases with one sandbox-only AF_UNIX skip plus validation.
- `git diff --check`: PASS.

## Unaffected paths sampled

Checksum selection remains exact and machine-verifiable; English README has no pinned experimental install command; runtime, Policy, Schema, Skill, CI workflow, and packaged resources are unchanged.
