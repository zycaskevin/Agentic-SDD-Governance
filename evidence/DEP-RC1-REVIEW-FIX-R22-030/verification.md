# Verification

## Green command and result

Engineering verification is Green: source validation, CI contract verification, focused hostile-boundary suites, 445 passing source tests plus 14 platform/sandbox skips, native Linux AF_UNIX, package build/Twine, offline bundle, and fresh installed-wheel smoke all pass. The complete repository suite remains deliberately non-Green by one contract assertion because `.sddgov/decisions.json` does not yet contain the verified Owner-signed `DEC-RC1-APPROVER-AUTHORITY-R22` receipt.

## Before/after evidence

Before R22, independent and CodeRabbit review reproduced false-success transaction boundaries, unsafe or incomplete cleanup, release and Broker close-order problems, a Darwin fixed-path alias failure, workflow/import and release-inventory defects, an L1/L2 authority mismatch, and an Owner experience that exposed machine receipt mechanics. After the engineering changes, targeted regression suites and installed-wheel/native verification pass; the L2 classifier emits exact `ACTION_REQUIRED` with exit code 2 for the bound decision artifact, the Agent CLI can only render the card, and the separate Owner client owns the A/B and external-signer boundary.

## Remaining limitations

- Owner approval is not inferred from chat text. Green/Proof transition, atomic commit, Gate, independent signature, and merge remain blocked until a valid Ed25519 L2 receipt is verified against a separately controlled public approver store and imported.
- Hosted macOS validation and CodeRabbit final review apply to the future exact R22 Gate Head and cannot be claimed from this uncommitted builder workspace.
- Actual `/etc` provisioning, key custody, service installation, and package publication remain separate L3/external actions.
- Forward correction: the immutable Red artifact says “459 passed, 14 skips, 1 expected failure.” The exact unittest result was 460 executed = 445 passed + 14 skipped + 1 expected authorization failure. The Red artifact is preserved rather than rewritten; this correction is authoritative for the count.
