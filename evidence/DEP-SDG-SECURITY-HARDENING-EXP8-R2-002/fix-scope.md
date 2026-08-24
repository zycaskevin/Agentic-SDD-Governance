# Fix Scope

## Smallest sufficient change

Close only the reproduced authority, CI semantics/filesystem, redaction FIFO, Evidence transaction/attachment, rollback, and protected-inventory boundaries. Preserve the approved L0/L1 autonomy contract and all existing L2/L3 signature boundaries.

## Files or components in scope

`src/sddgov/{autonomy,ci_guard,evidence,redaction,merge_gate}.py`; canonical and packaged Hard Gates, Redaction Gateway, and protected-files policy; hostile tests for autonomy, CI, Evidence, Merge, Reviewer, and repository contract; experimental.8 Work Package/DEP/Changelog/Roadmap records.

## Explicit non-scope

Production deployment, credentials, real Muse data, Billing, provider configuration, stable release, public release publication, and new Product behavior.

## Blast radius

Local governance classification, CI-cost verification, Evidence collection/redaction/attachment, and Merge rollback validation. The broadest compatibility change is rollback v2: free-form command fields are deliberately rejected in favor of the allowlisted declarative contract.
