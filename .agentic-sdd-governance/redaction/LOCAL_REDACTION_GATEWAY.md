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
8. DEP creation, Collector input, redaction, strict verification, attachment output, and DEP control-document writes retain verified base/source/DEP/zone/output directory descriptors through source reads, same-directory temporary writes, and atomic replacement; a pathname check followed by a pathname reopen is not sufficient. `attach` binds the exact in-memory summary/manifest snapshot to a framed SHA-256 in its content and default filename, stages output, makes the final control check its linearization point, and publishes with no-clobber semantics. A swap before that point removes only staging; a later control generation remains distinct and an existing or later destination writer is preserved. Parent replacement during an operation fails closed. Verification must then recompute output size and SHA-256 and match the exact source-to-output association.
9. Bind each artifact to its Collector, immutable input suffix, and detected media type. `browser-har` or detected HAR content remains blocked even when a caller supplies a misleading text label.
10. Open Collector input non-blocking and accept only a stable regular file. Reject FIFO/device/socket inputs and every intermediate symlink component before reading bytes.
11. Text redaction applies both inventory-driven replacement and built-in provider credential detectors, then rescans the output. A detected credential identifier that survives redaction fails closed. Clean zero-match synthetic text remains valid; an empty inventory alone is not evidence of a leak.
12. Collector/redaction updates are transactional at the DEP boundary: candidate controls are checked against their exact prior generation, replacement uses a no-clobber claim/publish sequence, a failure removes only artifacts still owned by that operation, and any later writer is preserved. A failure after the complete new generation was published is treated as a committed operation instead of destructively rolling it back. Pending control, redaction, or attachment staging is a strict-verification error and must be recovered or removed locally before Proof.
13. A single source file is limited to 10 MiB and a logical text line to 1,048,576 decoded characters. Larger inputs fail before publication and must be recollected as a bounded excerpt or safe summary. Eligible UTF-8 text is decoded and redacted in 64 KiB chunks; logical lines, local user paths, and private-key state span chunk boundaries so a sensitive value split by an I/O boundary cannot bypass a rule. Unterminated private-key blocks fail closed.

The built-in redactor is conservative. Streaming bounds memory and reduces accidental disclosure; it does not certify that a package is legally anonymized.
