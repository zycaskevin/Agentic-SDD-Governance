# Fix Scope

## Smallest sufficient change

- Reuse the synthetic pilot behind a top-level offline Demo with deterministic assertions and concise output.
- Expand English onboarding and split installation into fast trial and controlled verified routes.
- Prepare RC1 metadata, isolated OIDC publishing, artifact checks, and fresh-wheel smoke automation without performing a public upload.
- Add a non-consuming L3 Broker readiness command, a minimal root-managed Broker daemon protocol surface, service templates, and owner key lifecycle documentation without provisioning real identities.
- Add a trusted redaction input ceiling and a stateful cross-chunk text scanner whose output is equivalent to bounded whole-text redaction for supported patterns.
- Add recovery and rollback documentation that preserves Gate failure semantics.
- Add measurement-only Monorepo rollback benchmarks before considering algorithm changes.

## Files or components in scope

- `src/sddgov/`, `tests/`, `demo/`, `benchmarks/`, `docs/`, `templates/`, `.github/workflows/`, package metadata, README files, Work Package/DEP records, and canonical/packaged/installed governance copies required by repository parity tests.

## Explicit non-scope

- Real TestPyPI/PyPI upload, GitHub Release publication, repository-environment mutation, real Owner/reviewer key generation, root service installation, production nonce consumption, real user data, paid infrastructure, and changes that broaden L0-L3 authority.
- Production mock Broker flags, caller-selected trust paths, rollback bypasses, and affected-path-only Merge proof.

## Blast radius

- Redaction changes affect every text Evidence artifact and therefore require full evidence-flow and adversarial regression coverage.
- CLI and Broker readiness additions affect autonomy imports and packaging but must not change existing evaluation outcomes.
- Publishing workflow and package metadata affect release artifacts but not runtime authorization.
- Documentation and installed governance copies affect repository parity hashes and `doctor`; regenerate intentionally and verify exact equality.
