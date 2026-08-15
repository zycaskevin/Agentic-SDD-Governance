# Local Redaction Gateway

The gateway is a release boundary, not a cosmetic filter.

```text
collector output
  -> private/raw (local only)
  -> deterministic text redaction
  -> manual review for screenshots, traces, archives, and other binaries
  -> shareable/artifacts
  -> verify
  -> attach
```

## Non-negotiable rules

1. Never attach `private/raw` paths to an Issue, Commit, PR, Changelog, chat, or external service.
2. Remove private keys, credentials, authorization headers, cookies, JWTs, passwords, and named secret fields.
3. Mask email, phone, payment-like numbers, patient identifiers, and customer identifiers unless the approved test fixture is demonstrably synthetic.
4. Treat screenshots, every HAR archive, Playwright traces, videos, database dumps, and crash archives as blocked. The MVP has no signed manual-derivative receipt, so these artifacts cannot enter `shareable/artifacts` through the generic text redactor.
5. Do not weaken redaction to make `verify` pass. Replace the artifact with a safe derivative or document why it cannot be shared.
6. L2/L3 evidence that contains production, medical, payment, or authentication data stays local unless a specifically authorized destination and minimum disclosure are recorded.
7. Reject symlinked input, output, DEP zones, and control files. Reject path escape and duplicate destinations; never follow a link to read or overwrite a file outside the DEP.
8. DEP creation, Collector input, redaction, strict verification, attachment output, and DEP control-document writes retain verified base/source/DEP/zone/output directory descriptors through source reads, same-directory temporary writes, and atomic replacement; a pathname check followed by a pathname reopen is not sufficient. `attach` uses the exact in-memory summary/manifest snapshot checked by strict verification and rechecks both control-file identities before output. Control-file or parent replacement during an operation fails closed. Verification must then recompute output size and SHA-256 and match the exact source-to-output association.
9. Bind each artifact to its Collector, immutable input suffix, and detected media type. `browser-har` or detected HAR content remains blocked even when a caller supplies a misleading text label.

The built-in redactor is a conservative MVP. It reduces accidental disclosure; it does not certify that a package is legally anonymized.
