# Work Package: RC1 Developer Experience and Production Readiness

## References

- Issue: `#22`
- Baseline: `main` at `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`
- SDD: `docs/AUTONOMOUS_DEVELOPMENT_V1_2.md`, `docs/HARD_GATES_V1_2.md`, `docs/EVIDENCE_DRIVEN_SDD.md`, and `docs/CI_COST_GUARD.md`
- Risk: L1 cross-module security, release-readiness, packaging, and developer-experience work; public TestPyPI/PyPI publication, real Owner key provisioning, and root service installation remain separate external actions
- Evidence: `DEP-RC1-REVIEW-FIX-R10-018` (authoritative); `DEP-RC1-REVIEW-FIX-R9-017`, `DEP-RC1-REVIEW-FIX-R8-016`, `DEP-RC1-REVIEW-FIX-R7-015`, `DEP-RC1-REVIEW-FIX-R6-014`, and `DEP-RC1-REVIEW-FIX-R5-013` are immutable predecessor packages.

## Objective Contract

- Outcome: make the first SDG experience understandable in 30 seconds, prepare a safe `0.2.0rc1` distribution path, close the known redaction and L3 operational-readiness gaps, document recovery, and measure Monorepo rollback performance without weakening exact-tree verification.
- Success metric: the demo is deterministic; English and Traditional Chinese onboarding are materially equivalent; fast and controlled installs are tested; release artifacts pass fresh-wheel smoke tests; L3 readiness is diagnosable; redaction is bounded and cross-chunk safe; recovery documentation is executable; and the Monorepo benchmark reports reproducible measurements.
- Keep condition: Candidate code never becomes its own trusted verifier; no mock or break-glass path grants production authority or reports a false Gate PASS; no raw Evidence, private key, credential, or real user data enters the repository.
- Rollback condition: revert this Work Package if it weakens fail-closed action classification, trusted-Base verification, redaction, exact-tree rollback proof, key separation, or hosted CI cost controls.

## Executable Scope

1. Add a one-command, synthetic 30-second demo that exposes the strongest allow/block/redact properties without using real data or network access.
2. Align the English README with the Traditional Chinese Profile, L0-L3, installation, lifecycle, and limitations content; document fast and controlled installation paths.
3. Prepare version `0.2.0rc1`, a separate TestPyPI/PyPI Trusted Publishing workflow, attestations, build validation, and a fresh-wheel Codex/Hermes smoke test.
4. Document Owner key ceremonies per trust domain, rotation, revocation, backup, and loss recovery; provide root-managed Linux/macOS Broker service assets plus an L3 readiness diagnostic that never consumes a real nonce.
5. Bound redaction input size before allocation and implement deterministic streaming text redaction that preserves matches spanning read chunks.
6. Document the required single rollback commit, squash workflow, and an out-of-band break-glass incident path that never bypasses or relabels a failed Merge gate.
7. Add a reproducible Monorepo rollback benchmark and preserve full-tree equality unless measurements prove a safe optimization is required.
8. Keep canonical, packaged, and installed Governance resources synchronized where protected documentation or policy references change.
9. Close the PR #29 review findings: descriptor-bind release inputs, preserve Broker service availability after transient accept failures, reject ambiguous CI exemptions, close Windows-path and partial-key-marker redaction gaps, and separate proof correctness from benchmark latency decisions.
10. Close the PR #30 review findings: bind release directory generations, bound collector input before buffering, recursively scan shareable Evidence, validate exact service hardening, reject stale CI exception mappings, and align release/report/runbook contracts without fabricating the independent Review receipt.

## Acceptance Tests

- `demo/run.sh` completes with a concise PASS transcript in an offline synthetic temporary directory and fails nonzero when any demonstrated invariant is false.
- English README includes the Profile and L0-L3 tables, fast trial install, controlled verified install, first demo, managed files, lifecycle commands, and experimental limitations.
- Package metadata reports `0.2.0rc1`; built wheel and sdist pass metadata checks; a fresh virtual environment installs the wheel and passes version, `validate`, Codex/Hermes `setup-agent`, `doctor`, and offline pilot checks.
- The publish workflow is separate from `pull_request_target`, uses least-privilege permissions, a protected environment, OIDC Trusted Publishing, pinned actions, TestPyPI before PyPI, and default attestations.
- L3 readiness reports structured checks for runtime context, fixed socket path, root-owned non-writable parent chain, socket ownership/mode/type, non-root Agent identity, and a bounded non-consuming health handshake; normal install Doctor remains valid without L3.
- Broker service assets install no credentials or keys and their verification tests run without performing a live privileged installation.
- Redaction rejects inputs over the trusted limit before unbounded allocation and detects credentials/private keys whose matches cross internal read chunks; symlink, hardlink, FIFO, transactional, and report integrity guarantees remain Green.
- Recovery documentation clearly distinguishes preparation, authorized operational recovery, incident evidence, and Gate PASS; no caller-controlled override flag is introduced.
- The Monorepo benchmark records fixture size, Git version, elapsed time, return status, and exact-tree result; any optimization must retain an independent full-tree equality assertion.
- Full unit tests, repository validation, CI Guard, Local Green, canonical/package/install parity, package build, and fresh-wheel smoke tests pass.
- Release hashing, archive parsing, and copies consume one descriptor-bound input generation and fail closed on mutation or pathname replacement; transient GitHub API retries remain bounded to connection and 5xx failures.

## Non-scope and External Boundaries

- Do not publish to TestPyPI or PyPI, create a public GitHub Release, modify GitHub environments/rulesets, or push credentials without the required external authorization and working repository authentication.
- Do not generate, import, reveal, or store a real Owner private key in the repository, chat, Evidence, CI, or Agent workspace.
- Do not install a root service or write `/etc/sddgov`, `/run/sddgov`, or `/private/var/db/sddgov` during autonomous development.
- Do not add a production `--mock-broker`, caller-selected Broker path, rollback bypass, affected-path-only proof, or automatic force-push recovery.
- Do not claim empirical superiority over other governance systems from fixture-only results.

## Verification Plan

- Preserve a Red reproduction for unbounded redaction input and missing L3 operational diagnostics before implementation.
- Add targeted unit and integration tests for every new command, parser, file-boundary, workflow contract, documentation invariant, and benchmark result schema.
- Run the original Red checks, focused suites, full Local Green, package build, and a fresh-wheel smoke test.
- Before package construction, run `PYTHONPATH=src .venv/bin/python -m sddgov.cli validate .`; only a successful source validation may proceed to `python -m build --no-isolation` and fresh-wheel verification.
- Complete and strictly verify `DEP-RC1-REVIEW-FIX-R10-018`; generate a local PR attachment block only from redacted shareable artifacts. R10 records the exact PR #31 review, GraphQL thread IDs, and `discussion_r...` URLs; R9, R8, R7, R6, and R5 remain predecessor evidence rather than current authority. A collector UUID or redacted numeric review suffix is not used as GitHub identity.
