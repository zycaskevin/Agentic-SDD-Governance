# Fix Scope

## Smallest sufficient change

Bind staged redaction, Evidence controls, and attachments to their original identity, byte size, and digest; keep guards across pre-commit close; atomically claim cleanup generations; make parent leases reconcile publications; detect cross-line sensitive fields and native/escaped WSL paths; remove pathname use from supplied-dirfd calls; and close the release/control-plane provenance gaps.

## Files or components in scope

`src/sddgov/{evidence,redaction,fs_security,broker}.py`, release helpers and workflows, L3 runbooks and service assets, mirrored governance resources, Work Package provenance, and focused regression/contract tests.

## Explicit non-scope

No package publication, root service installation, production operation, real Owner key, new approval scope, caller-controlled path canonicalization, or historical Evidence rewrite.

## Blast radius

Evidence/redaction transactions, Broker cleanup, descriptor-bound report creation, release provenance, and L3 operational readiness are affected. One atomic revert restores the exact Base product tree while audit Evidence remains.
