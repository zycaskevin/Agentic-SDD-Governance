# Work Package: SDG Security Hardening

## References

- Issue: #9
- Baseline: `v0.2.0-experimental.6` / `d03d0a855d32fbfb8b42c29db2f008263de0f806`
- SDD: `docs/HARD_GATES_V1_2.md`
- Evidence: `DEP-SDG-SECURITY-HARDENING-001`
- Risk: L2, explicitly requested by the Owner

## Objective Contract

- Outcome: make the experimental governance gates fail closed across verifier provenance, Evidence integrity, filesystem boundaries, and L2/L3 authorization.
- Success metric: every confirmed adversarial case fails deterministically, normal L0/L1 engineering remains autonomous, and a disposable synthetic Muse pilot completes without real data or Production authority.
- Guardrails: no Production operation, credential, private signing key, real Muse data, Billing change, or stable-release publication.
- Keep condition: the complete existing suite plus new adversarial tests, package smoke, strict DEP, and synthetic pilot remain Green.
- Rollback condition: revert this bounded Work Package if trusted verification cannot remain independent or routine L0/L1 work becomes dependent on owner approval.

## Scope

- Separate the trusted verifier implementation and workflow definition from candidate PR code.
- Recalculate every portable Evidence artifact path, type, size, digest, and manifest/report association; verify local raw artifacts when present.
- Reject DEP path escape, collector/redaction symlinks, unexpected filesystem objects, and duplicate labels or manifest paths.
- Replace caller-created L2 authority with a separate-identity trust root and owner-signed artifacts whose current bytes are recalculated on reuse.
- Bind L3 receipts to repository, project, environment, scope, category, target, parameters, and effects; require a clone-external atomic nonce broker before `CONTINUE`.
- Require Base revocation to override stale external Reviewer bootstrap state.
- Require complete, mutually exclusive raw-to-redacted/blocked associations; block HAR and unknown/binary types from the deterministic text route.
- Reject symlink side effects, hardlinks, and pathname reopen TOCTOU in Evidence collection/redaction.
- Bind Collector identity, immutable source suffix, and detected media type; retain verified DEP/zone directory descriptors through final Evidence reads, verification, and control-document mutation.
- Require a separate root-controlled Runtime Context for L3, reject root Agent execution, use a root-provisioned Unix nonce service on fixed platform paths, and return the exact authorized payload to the executor.
- Pin privileged GitHub Actions by full commit SHA and install only hash-locked verifier dependencies.
- Add a synthetic, disposable Muse-compatible pilot with no real user content or external authority.
- Update schemas, docs, packaged resources, adapters, version, Changelog, and Roadmap.

## Non-scope

- Production deployment or migration.
- GitHub Billing or runner provisioning.
- Owner/Reviewer private-key creation or custody.
- Processing real Muse relationship data.
- Publishing a stable release.

## Verification Plan

1. Preserve each confirmed failure as an adversarial regression test.
2. Run targeted Evidence, autonomy, merge, installer, and repository-contract tests.
3. Run the complete local suite and `sddgov validate`.
4. Build and install the package in a fresh environment.
5. Install into a disposable synthetic Muse clone and run the pilot assertions.
6. Complete and strictly verify the redacted DEP.
7. Repeat fresh independent review until P0/P1 is zero; only then sign the exact Merge gate. Treat this bootstrap PR's old Base workflow as non-authoritative and use the new trusted workflow for subsequent PRs.
