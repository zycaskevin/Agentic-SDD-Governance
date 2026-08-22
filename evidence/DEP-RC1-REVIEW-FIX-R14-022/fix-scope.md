# Fix Scope

## Smallest sufficient change

Replace the four unsafe contracts without weakening trusted-Base, signed
review, Evidence, approval, or exact-tree rollback gates.

## Files or components in scope

- Release input/lock floors and isolated publish-test environment.
- Broker identity cleanup, bounded private logging, and systemd throttling.
- Darwin unified logging and complete removal of the newsyslog asset.
- Canonical, `.agentic`, embedded, installer, Doctor, and documentation parity.
- CI interpreter provenance, bundle counts, redaction failure preservation,
  private snapshot modes, and focused review-requested contract tests.

## Explicit non-scope

No trusted verifier is weakened. Historical R6-R13 Evidence is not rewritten.
No package is published, protected environment changed, key generated, root
daemon installed, production data touched, or superiority claimed.

## Blast radius

Release preparation, CI reporting, Broker services, macOS logging, installed
governance assets, and package reports. External application code is unaffected.
