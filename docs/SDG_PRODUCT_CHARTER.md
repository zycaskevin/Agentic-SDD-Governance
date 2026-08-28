# SDG Product Charter

Status: implemented as a locally verified AF27-mainline candidate and submitted
in PR #57; not merged, configured, or released

## Why SDG exists

SDG exists so autonomous agents can keep software work bounded, testable,
reviewable, recoverable, and honest without making the product owner supervise
routine engineering. Governance should reduce owner workload while containing
real risk.

## Product rule

> Invisible by default. Appear only when risk or real-world effects rise. Never
> ask the Owner to solve work that agents or deterministic checks can solve.

SDG is risk- and effect-centric, not approval-centric. The governing question
is not “Which workflow step is this?” but “What capability is being exercised,
and does it create an external, destructive, privileged, financial, secret, or
irreversible effect?”

## Three channels

### 1. Development

Coding, tests, lint, PR creation, review, and finding repair are agent work. Owner
operations are zero. SHA-256, Base/Head references, receipts, TTY, SSH agent,
signer, Broker, and DEP internals are not Owner UI.

### 2. Release readiness

Full CI, build, integration tests, independent review, CodeRabbit, rollback
validation, and artifact verification may be strict, but remain agent/machine
work. A PASS means “ready for release,” never “released.”

### 3. Production action

Public publishing, Production deployment, Production database migration, Secret
or IAM changes, real payment, and destructive or irreversible operations cross
the reality boundary. SDG presents one clear action, destination, impact, and
rollback statement and asks for at most one explicit approval. Native platform
controls are preferred.

Strong authorization is useful only when it creates a distinct trust boundary.
A digest copied between windows on the same compromised device is integrity
theatre, not strong identity verification.

## Merge and review

Merge is L1 by default. It becomes L3 only when the repository's actual
configuration makes that merge trigger an L3 effect. Independent review remains
available, but the Main Agent receives findings and coordinates repair; the Owner
is never a reviewer dispatcher or message relay.

Findings returned by an automated reviewer such as CodeRabbit must be repaired.
A successful provider status that explicitly skipped review is not a review.
After one automatic attempt for an exact revision, provider skip or
unavailability uses the bounded fallback of a signed independent review, the
full Merge Gate, and hosted CI. The system does not retry indefinitely or route
the provider outage through the Owner.

## What is retained

Tests, CI, rollback, redaction, evidence, exact references, hashes, artifact
verification, independent review, Broker, Ed25519, hardware keys, and audit
receipts remain available. The first group stays machine-operated. The strong
authorization group is removed from the default path and reserved for regulated
or genuine L3 use with a separate trust boundary.

Installer success means governance routing and reference resources are present.
It never means that Broker, Owner signing, or strong authorization has been
installed or activated.

## Current gap

The completed runtime slices let team-standard record one plain-language L2
choice and keep effect-free Merge and release readiness at L1 with zero Owner
operations. Actual Production deploy and public publication are now one exact
L3 operation. This repository now verifies that its own SDG install and hosted
governance workflow remain deactivated, while the external-project Installer
continues to work and reports strong authorization as inactive. The Pull
Request candidate now implements and verifies the separate exact artifact
handoff from release readiness into publication, and the primary product
documentation has been migrated. Remaining readiness is independent review and
Merge, plus GitHub Environment protection, Trusted Publishing, the exact
release tag, and registry publication. None of those external effects has
occurred, so the product reset is not yet merged or released.

The executable source of truth for this direction is
`specs/sdg-product-contract.json`.
