# Verification

## Green command and result

The engineering preview is bounded but not yet Green/Proof: source validation and CI contract verification pass; the current Owner approval, autonomy, and shared-filesystem suite reports 93 pass plus 1 sandbox skip; and the complete source suite reports 472 pass plus 14 platform/sandbox skips. One repository-contract assertion remains intentionally Red because `.sddgov/decisions.json` does not yet contain an imported Owner-signed `DEC-RC1-APPROVER-AUTHORITY-R22` receipt verified through `sddgov decision verify-product`. Package, native, rollback, hosted, and final Gate proof must be regenerated for the future exact reviewed revision after the decision is valid.

## Before/after evidence

Before R22, independent and CodeRabbit review reproduced false-success transaction boundaries, unsafe or incomplete cleanup, release and Broker close-order problems, a Darwin fixed-path alias failure, workflow/import and release-inventory defects, an L1/L2 authority mismatch, and an Owner experience that exposed machine receipt mechanics. In the current engineering preview, targeted source regression suites pass; the Agent CLI remains non-signing; the separate Owner client accepts only the semantic A/B choice on `/dev/tty`; and the reviewed installed-client digest, exact repository, trust domain, assumptions, key ID, and validity are machine-bound without expanding the trusted Base receipt schema.

## Remaining limitations

- Owner approval is not inferred from chat text. Green/Proof transition, atomic commit, Gate, independent signature, and merge remain blocked until a valid Ed25519 L2 receipt is verified against a separately controlled public approver store and imported.
- Hosted macOS validation and CodeRabbit final review apply to the future exact R22 Gate Head and cannot be claimed from this uncommitted builder workspace.
- Actual `/etc` provisioning, key custody, service installation, and package publication remain separate L3/external actions.
- Forward correction: the immutable Red artifact says “459 passed, 14 skips, 1 expected failure.” The exact predecessor unittest result was 460 executed = 445 passed + 14 skipped + 1 expected authorization failure. The current preview result is 487 executed = 472 passed + 14 skipped + 1 expected authorization failure. The Red artifact is preserved rather than rewritten; this correction is authoritative for the counts.
