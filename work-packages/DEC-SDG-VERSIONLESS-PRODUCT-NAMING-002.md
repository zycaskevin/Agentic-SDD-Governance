# Decision: SDG product concepts use version-independent names

Decision ID: `DEC-SDG-VERSIONLESS-PRODUCT-NAMING-002`

Status: approved product direction

Decision date: 2026-08-27 Asia/Taipei

Decision source: the Owner directly instructed the Agent to continue the reset
without using `v2`-style product naming.

## Decision

Product concepts, contracts, charters, Work Packages, tests, branches, and active
documentation use stable semantic names such as `SDG Product Contract`,
`Effect Boundary`, and `Product Reset`. They do not use a generation label such
as `v2`.

Package versions, schema versions, and historical compatibility records may keep
their real version identifiers where changing them would alter a public protocol,
artifact identity, or migration history. Those identifiers are data, not product
branding.

## Reopen conditions

Reopen only if SDG intentionally supports multiple simultaneous incompatible
product generations that require distinct public identities.
