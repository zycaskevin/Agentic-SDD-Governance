# Release readiness and publication handoff

Status: implemented locally; external release configuration remains `NOT_READY`.

## Plain-language contract

Release readiness proves that one candidate is ready. It cannot publish, deploy,
change secrets, or ask the Owner to handle Git references or hashes.

Publication accepts only one successful readiness run for the exact release tag.
Before any approval is requested, the workflow verifies the repository, workflow
identity, run and attempt, tag, commit, default-branch ancestry, artifact name,
every public asset digest, the exact immutable Owner reviewer identity, and that
TestPyPI, GitHub Releases, and PyPI do not already contain this release. The Owner
sees one native GitHub Environment choice: approve or reject publication of the
named release to all three targets.

## Required GitHub configuration

Create one Environment named `release` only when the release candidate is ready:

- require exactly the Owner identity recorded by immutable numeric ID and type in
  `policies/release-authority.json` as reviewer;
- enable prevention of self-review;
- disable administrator bypass;
- allow only the repository's default workflow branch, because the trusted
  `workflow_run` publication verifier executes from that branch;
- keep the repository public for this RC so trusted preflight can read public
  Environment metadata without an extra token or secret; a future private-repo
  release path requires a separately reviewed read-only authentication design;
- configure TestPyPI and PyPI Trusted Publishers for `.github/workflows/publish.yml`
  and Environment `release`.

Release helpers reject oversized repository, ref, tag, workflow, authority, and
handoff inputs before contacting GitHub or a registry. HTTP bodies, Git result
capture, Git/CLI subprocesses, pip retries, and release notes also have explicit
limits; exceeding any limit fails closed before a publication effect.

The identity that dispatches `release-candidate.yml` must be an automation identity
distinct from the Owner. Otherwise GitHub's prevent-self-review control may also
prevent the Owner from approving the publication job. Do not solve that problem by
asking the Owner for a token, terminal command, SHA, signer, or reusable receipt.

## Exact automated sequence

1. After reviewed Merge, automation creates or selects the exact release tag and
   dispatches `release-candidate.yml` at that tag.
2. Ubuntu and macOS run the complete machine proof. The tagged Ubuntu job builds,
   inventories, and smoke-tests the release artifact.
3. GitHub starts `publish.yml` from the completed readiness event. One stable
   per-version concurrency key serializes duplicate dispatches. Its unprivileged
   preflight verifies the exact Owner reviewer, refuses any partial or completed
   prior publication, and re-packages the exact handoff.
4. The single `release` job waits for the Owner's native approval. No publication
   credential or write permission is available to the preflight job.
5. After approval and before the first effect, the protected job rechecks that
   this version is still absent from TestPyPI, GitHub Releases, and PyPI. If any
   target is occupied it aborts without publishing; otherwise it publishes and
   downloads the exact wheel from both registries for byte equality and
   fresh-wheel smoke. Rejection publishes nothing.

## Current external readiness

This repository change does not create the Environment, provision its reviewer or
secret, configure either Trusted Publisher, create a tag, dispatch a workflow, or
publish an artifact. Those facts must be checked live before any release claim.

If a protected publication job partially changes an immutable registry and then
fails, a later dispatch stops before another Owner prompt. Do not blindly rerun and
do not use `skip-existing`. Record the exact changed targets and either execute a
bounded recovery plan or issue a new candidate version.
