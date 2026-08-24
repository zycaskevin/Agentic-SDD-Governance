# Fix Scope

## Smallest sufficient change

Add bounded quoted-sensitive-field state for password, secret, patient, and
customer identifiers. Hold only the candidate field, detect an unescaped
closing quote, then pass the completed field through the existing private-key
and ordered stream-rule pipeline. Fail closed on EOF, excess retained
characters, or a backslash escaping a physical line ending. Correct the two
README predecessor-version lines found by the same exact review.

## Files or components in scope

`src/sddgov/redaction.py`, `tests/test_redaction.py`, `README.md`,
`README.zh-TW.md`, the current Work Package, its repository-contract assertion,
and this authoritative DEP.

## Explicit non-scope

No rule weakening, no raw Evidence publication, no change to the Owner approval
client, Decision request, trust root, receipt semantics, Broker, release
benchmark behavior, or Production operation. The CodeRabbit Owner-choice and
missing-Git suggestions are not applied because independent probes found no
current authorization or availability defect.

## Blast radius

The change is limited to streaming text redaction and onboarding text. Existing
transactional publication and replacement-preservation cleanup remain the
failure boundary. None of the eight Owner-client identity files changes, so
the already signed L2 authority receipt remains exactly bound.
