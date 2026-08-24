# Fix Scope

## Smallest sufficient change

Retain one repository snapshot for the complete product-decision verification,
make envelope verification consume that supplied snapshot, and compare the
already verified receipt row without reopening it.  Enforce every smaller
cache-hit bound.  Add a required bounded Local Green per-command timeout.

## Files or components in scope

`src/sddgov/autonomy.py`, `src/sddgov/fs_security.py`, `src/sddgov/ci_guard.py`,
their regression tests, CI Cost Guard schemas/templates/documentation/mirrors,
the managed manifest, and the R27 Work Package/decision binding.

## Explicit non-scope

No private-key handling, root trust-store or signer provisioning, production
operation, reviewer receipt, release publication, Broker authority, Evidence
withdrawal rewrite, or weakening of trusted-Base verification.

## Blast radius

Product-decision reuse, Owner approval input bounds, and Local Green execution.
The fixed public authority scope is unchanged, but changes to the reviewed Owner
client source require one fresh semantic Owner decision after independent
pre-sign review.
