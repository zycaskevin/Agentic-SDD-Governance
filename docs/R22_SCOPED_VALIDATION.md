# R22 Scoped Local-Green Validation (Draft)

## Goal

R22 is an Owner-authority verification, not a test of unrelated feature code.
The proposed policy runs R22 validation only when a trusted, exact change set
touches an R22 authority input, R22 verifier, protected decision artifact, or
the Gate configuration that selects the rule.

## Safety invariant

The rule is fail closed. Missing, empty, malformed, or candidate-supplied path
information requires R22 validation. The future executor must derive the
change set from a trusted Base-bound diff. Changing the scope classifier,
the Gate contract, the Owner-client source chain, decision record, trust data,
or packaged governance resources always requires R22.

## Status

The classifier is an offline testable foundation only. AF27 and all other
current Local Green invocations retain the existing unconditional R22 command.
Enabling this policy is a separate L2 decision and protected-file review; it
does not authorize production, signing, Owner-key provisioning, or deployment.
