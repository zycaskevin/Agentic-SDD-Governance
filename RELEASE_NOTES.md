# v0.2.0rc1 Release Notes

## Outcome

`0.2.0rc1` turns the experimental.9 security core into a lower-friction release candidate without weakening its authority boundaries. It preserves the stricter fail-closed Draft guard, and adds a 30-second offline demonstration, direct pre-release installation, fresh-wheel validation, an isolated OIDC publication chain, an operable L3 Broker, Owner key lifecycle guidance, streaming redaction, and documented squash/break-glass recovery.

This remains an experimental pre-release, not a compliance certification. External publication and real trust-root provisioning are separate controlled actions; this file must not be interpreted as proof that TestPyPI or PyPI publication has already occurred.

## Install after publication

Fast synthetic trial:

```bash
python3 -m venv .venv-sddgov
.venv-sddgov/bin/python -m pip install --pre 'agentic-sdd-governance==0.2.0rc1'
test "$(.venv-sddgov/bin/sddgov --version)" = "0.2.0rc1"
.venv-sddgov/bin/sddgov pilot quick
```

For a controlled Linux x86_64/CPython 3.12 installation, download the offline bundle and `SHA256SUMS.txt` from `v0.2.0rc1`. Machine verification covers the archive, exact runtime lock, project wheel, and dependency wheelhouse before an offline `--require-hashes` install. Do not ask a human to copy, paste, or visually approve a digest.

## Main changes

- Offline `sddgov pilot quick` and `demo/run.sh` demonstrate authorized routine work, dangerous downgrade blocking, text redaction, binary fail-closed behavior, and strict DEP proof with synthetic data.
- `release-readiness.yml` performs the normal Ubuntu/macOS source, package, inventory, and fresh-wheel proof with no Owner operation. The manual, tag-only `release-candidate.yml` repeats that proof and uploads one immutable candidate artifact; neither workflow publishes anything.
- `publish.yml` starts only from the completed manual, exact-tag `release-candidate.yml` run—not from the pull-request `release-readiness.yml` workflow—machine-verifies the repository, workflow, run, tag, commit, trusted verifier, default-branch ancestry, artifact name, and complete asset inventory, and then waits once at the native `release` Environment. Only that one protected job receives `contents: write` and `id-token: write`; external Actions use full commit SHAs and PyPI attestations are enabled.
- `sddgov broker doctor` checks platform, non-root Agent identity, root-owned Runtime Context, out-of-band Ed25519 trust, trusted fixed-path socket, and a read-only health response.
- The Broker provides an append-only root-owned nonce ledger, exact bounded protocol, fsync-before-success, and replay rejection, with reviewed systemd and launchd templates.
- Owner keys are separated by trust domain and have documented ceremony, rotation, revocation, compromise response, and loss recovery.
- Text redaction has a 10 MiB file cap, a 1 MiB logical-line cap, and 64 KiB streaming with cross-chunk UTF-8, credential, and private-key handling.
- Rollback operations document the single-parent proof, atomic feature-branch commit, GitHub squash-SHA mapping, forward recovery, and a time-bounded external break-glass process. There is no verifier bypass flag.
- A recorded 1k/10k/50k-file synthetic benchmark kept the complete exact Base-tree comparison; the 50k p95 was 0.017217 seconds on the recorded local environment, far below the predeclared 5-second investigation threshold.

## Required release transaction

Before marking this version published:

1. Freeze the exact candidate Head and run the complete local suite, `sddgov validate`, CI Cost Guard, current-install Doctor, strict DEP Proof, package build, Twine, and fresh-wheel smoke.
2. Obtain an independent protected-file review bound to the exact change and gate metadata digests.
3. Pass the trusted Base Merge verifier and required repository ruleset.
4. Configure one GitHub Environment named `release`: require the Owner reviewer, prevent self-review and administrator bypass, and allow only the default workflow branch. Configure TestPyPI and PyPI Trusted Publishers for workflow `publish.yml` and Environment `release`. Store the fine-grained read-only repository-administration token only as the Environment secret `RELEASE_CONFIGURATION_READ_TOKEN`. The readiness dispatcher must use an automation identity distinct from the Owner so the Owner can perform the one native approval.
5. Create and protect the exact `v0.2.0rc1` tag at the independently reviewed Merge result. Dispatch `release-candidate.yml` at that tag with the automation identity. A successful run automatically opens the publication preflight; the Owner never supplies its run ID or SHA.
6. Review the single GitHub Environment prompt for `v0.2.0rc1`. Approval performs the exact TestPyPI publish and byte-equality smoke, GitHub prerelease, PyPI publish, and PyPI byte-equality smoke in one protected job. Rejection performs no external publication.
7. Never blindly rerun after a partial registry transaction and never use `skip-existing`; first record which immutable targets changed, then use a bounded recovery plan or a new candidate version.
8. Verify the public PyPI project page, attestations, exact installed version, and offline quick demo from a new environment. Record URLs and immutable workflow/run identifiers in the release evidence.

## Important limits

- Root Broker installation, Runtime Context, trusted approver store, Owner private keys, and key recovery material remain outside the repository and Agent workspace.
- Broker `NOT_READY` blocks real L3 operations; it is not a request to substitute a mock or same-UID service.
- Redaction reduces accidental disclosure but does not certify legal anonymization. Binary Evidence remains fail-closed without an approved derivative.
- The synthetic monorepo and debugging fixtures validate bounded harness behavior, not superiority or universal capacity.
- MyHermes or any patient, customer, or payment system still requires an environment-specific key ceremony, Broker rehearsal, synthetic/staging pilot, incident drill, and separate authorization before real data.
