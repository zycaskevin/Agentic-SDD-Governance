# Reproduction

## Expected

R21 should have committed each Evidence/publication mutation only after all retained path leases, generation snapshots, descriptor closes, and directory durability checks succeeded. Cleanup must remove only its own generation and preserve later writers. Release and Broker cleanup must drain resources without masking the primary failure. The fixed approver authority source must be classified and approved as L2 before merge. An Owner must decide only the bounded product meaning; SDG must not ask the Owner to edit receipt JSON, calculate or relay hashes, paste a signature, expose a private-key path, or perform code review.

## Actual

The independent R21 review returned FAIL and created no receipt. CodeRabbit's exact-Head review also found actionable workflow, release-inventory, documentation, Broker-cleanup, and authority-classification issues. Additional builder reproductions showed that post-publication wrapper failures could be reported as success, partial release writes could leave an owned residual file because cleanup used the full expected digest, Darwin's logical `/etc` alias would be rejected by the fixed-path no-follow walker, and DEP tree cleanup did not generation-claim individual children. The only L2 path exposed an unsigned receipt template and required the Owner to manipulate signing mechanics manually; the Agent CLI had no bounded non-signing card surface and there was no separated Owner entry point.

## Deterministic steps

1. Review the exact R21 Gate Head and its independent FAIL verdict; confirm there is no R21 review receipt.
2. Inject a failure immediately after manifest, redaction-report, or summary publication; observe the predecessor implementation return success instead of rolling back the call-wide transaction.
3. Make a release writer return a short write and fail on its next write; observe cleanup compare the partial file against a full-file digest and retain the owned residual generation.
4. Evaluate the fixed `/etc/sddgov/trusted-approvers.json` walker under Darwin's platform-owned `/etc` alias; observe the no-follow path traversal reject the supported logical location.
5. Replace the Evidence root after a new DEP is published and add a later child before cleanup; observe predecessor recursive stat/unlink logic lacks a per-child generation claim.
6. Run the repository contract test; it must remain Red while `.sddgov/decisions.json` lacks `DEC-RC1-APPROVER-AUTHORITY-R22`.
7. Inspect the R21 CLI and Owner runbook; observe that the only path from validated `ACTION_REQUIRED` to import is a hand-built signed JSON envelope rather than one semantic A/B Owner action.

## Environment and preconditions

Baseline is the exact R21 Gate Head `1d226f4d9dc919ab7fc147391394b9e65f98e2a2` on the RC1 readiness branch. Reproductions use only synthetic temporary files and mocked failure boundaries; no real credentials, Owner private key, `/etc` write, root service installation, or Production operation is involved.
