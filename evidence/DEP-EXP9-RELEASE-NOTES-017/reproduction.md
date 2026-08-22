# Reproduction

## Expected

The public release notes describe the installed-wheel Cost Guard verification
without a downstream repository name, pull-request number, or unpublished-state
detail.

## Actual

One sentence contains all three forms of downstream-specific context. A
content-free privacy assertion therefore reports one prohibited match.

## Deterministic steps

1. Inspect the installed-wheel verification bullet under `Verified release
   boundaries`.
2. Run the bounded privacy assertion for downstream name, PR-number, and
   unpublished-state forms.
3. Observe `expected_matches=0`, `actual_matches=1`, and exit status `1`.

## Environment and preconditions

Exact Base/HEAD `4c2a1ca27c49e0db00550300ab5b2e3c6658a4eb` on
`codex/fix-exp9-release-note-disclosure`; no experimental.9 tag or Release has
been pushed.
