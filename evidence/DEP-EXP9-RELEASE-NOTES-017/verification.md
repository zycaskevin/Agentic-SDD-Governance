# Verification

## Green command and result

The bounded privacy assertion reports zero prohibited public matches and finds
the generic verified-behavior statement. `git diff --check` and `sddgov ci
verify` pass. Local Green runs 232 tests without failure (one sandbox-only
AF_UNIX skip) and validation passes.

## Before/after evidence

Red: content-free privacy assertion reports one prohibited public match. Green:
the same assertion reports zero, while the installed-wheel result and public
Cost Guard behavior remain stated.

## Remaining limitations

The exact downstream reproducer remains only in earlier governed Issue #44
Evidence. Fresh exact review, Hosted Governance, merge, artifact rebuild,
provenance signature, and public release remain separate gates.
