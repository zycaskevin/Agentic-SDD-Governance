# Fix Scope

## Smallest sufficient change

Introduce transaction-owned retained directory descriptors and complete generation verification for mutating Evidence entry points; make failure cleanup collision-safe and content-bound; repair close/fsync ordering in release and Broker helpers; correct the TestPyPI/import, release inventory, documentation, and Darwin fixed-alias contracts; bind the fixed approver source to one exact L2 decision artifact and receipt; and replace human receipt mechanics with a non-signing Agent card plus a separate Owner-terminal client that reconstructs and verifies the signed receipt through an Agent-inaccessible Ed25519 signer channel. Generic SSH confirmation is transport, not semantic approval; the Owner-controlled client or external signer must display and bind the exact card.

## Files or components in scope

- `src/sddgov/evidence.py`, `fs_security.py`, `redaction.py`, `trust.py`, `autonomy.py`, and `broker.py`.
- `src/sddgov/owner_approval.py`, `owner_cli.py`, the pre-import isolated `sddgov-owner` launcher, wheel RECORD/entry-point validation, and the installed-wheel smoke contract.
- `scripts/release_files.py`, release verification scripts, and the publish workflow.
- Focused hostile-boundary, package, workflow, and repository-contract tests.
- Canonical, managed, and packaged operator documentation plus the RC1 Work Package.
- `work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.md`, its machine-readable governed request, and the verified decision store after Owner approval.

## Explicit non-scope

No `/etc` write, real key generation/import, Broker installation/restart, TestPyPI/PyPI publication, GitHub Release, Production operation, policy downgrade, historical Evidence rewrite, or reviewer self-signing.

## Blast radius

The code changes affect Evidence mutation durability, public-output cleanup, release artifact construction, L3 Broker startup/shutdown cleanup, and L2/L3 approver lookup. Failures are fail-closed. Rollback reverts the single R22 product commit and reconciles managed governance from the trusted Base.
