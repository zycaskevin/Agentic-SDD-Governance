# Decision: SDG uses risk- and effect-centric governance

Decision ID: `DEC-SDG-EFFECT-BOUNDARY-001`

Status: approved product direction

Decision date: 2026-08-26 Asia/Taipei

Decision source: the Owner directly instructed the Agent to begin the SDG product
reset and supplied the three-channel product boundary in the current Codex task.

## Decision

SDG governs when risk and real-world effects rise. It does not govern each
ordinary engineering workflow step.

1. Development and release readiness are autonomous Agent/machine channels with
   zero Owner operations.
2. A genuinely unresolved L2 product choice uses one bounded plain-language
   interaction. Team-standard L2 does not require a terminal, digest, signer,
   Broker, or cryptographic receipt.
3. Every concrete L3 action requires exactly one explicit Owner approval. Native
   platform approval is preferred.
4. Broker, TTY, Ed25519, hardware-key, and receipt machinery is justified only
   when the action has a real external effect and the approval surface creates a
   distinct identity or trust boundary.
5. Merge is not intrinsically L3. It escalates only when the repository's actual
   configuration makes merge trigger a Production, secret, IAM, payment,
   destructive, irreversible, or public-publication effect.
6. Exact Git references and SHA-256 remain valuable machine integrity data and
   must never become Owner UI or a copy/paste task.
7. Independent review remains required where appropriate, but findings flow
   Reviewer Agent -> Main Agent -> Builder Agent without Owner relay.

## Supersession

This decision supersedes the approval-centric team-standard L2 product model in
`DEC-RC1-APPROVER-AUTHORITY-R22`. It does not delete the older security work and
does not weaken regulated/L3 controls at a genuine reality boundary.

## Reopen conditions

Reopen only if the selected product audience changes from normal software teams
to regulated-by-default use, or evidence shows that a zero-interruption
development/release-readiness channel permits an uncontained real-world effect.
