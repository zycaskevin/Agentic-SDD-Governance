# Fix Scope

## Smallest sufficient change

Correct the native harness and workflow provenance without changing the reviewed
Broker publication algorithm or weakening any security gate.

## Files or components in scope

- Short owner-only native/fresh-wheel temporary roots on POSIX.
- Fixed Darwin production staging-path boundary test.
- Dual-lock wheel build, isolated install, pip check, and installed-wheel import
  assertion in Linux/macOS native CI.
- Canonical/installed operations docs and R16 Work Package provenance.

## Explicit non-scope

No Broker protocol/receipt change, public package release, root service install,
production authority store, key generation, historical Evidence rewrite,
protected-environment mutation, or benchmark superiority claim.

## Blast radius

Native CI, test/fresh-wheel temporary paths, package provenance, managed docs,
and the current Work Package. Runtime application APIs and data schemas remain
unchanged from the R15 product candidate.
