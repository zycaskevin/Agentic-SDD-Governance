# Fix Scope

## Smallest sufficient change

Add a pure, fail-closed R22 path classifier plus its SDD, work package, and
synthetic tests. Do not wire it into CI Guard.

## Files or components in scope

`sddgov.r22_scope`, its tests, the scoped-validation SDD, and this work
package/evidence.

## Explicit non-scope

Changing `.sddgov/ci-cost-guard.json`, issuing or importing an Owner receipt,
production work, release, deployment, and any credential or trust-store action.

## Blast radius

None at runtime: no configured Gate invokes this module.
