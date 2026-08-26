# L2 Decision Contract: R22 Scoped Local-Green Validation

Decision ID: `DEC-R22-SCOPED-LOCAL-GATE-001`

Owner client binding: {"source_sha256":"feab8e03f188644ab056063ff6798df381636be1c592f69e320c096010facce6","version":"0.2.0rc1"}

## Exact scope

This decision authorizes only the activation of an R22 scoped Local-Green
rule. The rule may skip the R22 product-decision verification only when an
exact change set, derived by a trusted Base-bound verifier, is non-empty,
canonical, and contains no R22-protected path. Missing, malformed, ambiguous,
or candidate-supplied path data must require R22. The scope classifier, Local
Green contract, decision record, R22 request/documents, Owner-client source
chain, trust data, and packaged governance resources are R22-protected.

This decision does not authorize production, deployment, trust-store or key
provisioning, credential access, changing the content of R22 authority rules,
or skipping R22 for any protected change.

## Options

- A — activate the exact scoped Local-Green rule above.
- B — retain unconditional R22 validation for every Local-Green invocation.

Recommended: A. It permits unrelated offline engineering while preserving
fail-closed verification for every authority-bearing change.

Reopen condition: `scope_or_assumptions_change`.
