# Fix Scope

## Smallest sufficient change

Preserve the pilot subprocess status after rendering diagnostics; add a bounded
local-user-path rule to canonical, packaged, and installed redaction inventories;
make helper/test timeouts explicit; correct hosted-workflow wording; bind the
Work Package and executable rollback to R7; and remove duplicated test fixtures
and release-version literals without changing runtime authority.

## Files or components in scope

- Demo wrapper and its subprocess regression tests.
- Streaming/text redactor, rule inventory, gateway wording, installed-resource
  parity, and a repository-wide tracked-shareable path audit.
- Fresh-wheel helper timeout, release fixtures, Broker test fakes, benchmark
  assertions, CI diagnostic wording, and current Evidence contracts.
- R6 shareable derivatives regenerated from identical immutable raw sources to
  remove paths and correct the recorded execution count.

## Explicit non-scope

- No TestPyPI/PyPI/GitHub Release publication, tag, environment/ruleset change,
  Production action, real key provisioning, root service install, or nonce use.
- No self-signed independent review, review-thread resolution, workflow
  cancellation change, affected-path rollback weakening, or broad docstring churn.

## Blast radius

Runtime changes are limited to the demo exit boundary, path masking, timeout
configuration, and one diagnostic string. The sensitive effect is Evidence
shareability, so literal/escaped and cross-chunk path cases, every tracked Proof
DEP, full Local Green, packaging, and actual rollback receive explicit coverage.
