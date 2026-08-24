# Reproduction

## Expected

The current public installation examples select `v0.2.0-experimental.8`, retain machine verification through `SHA256SUMS.txt`, and do not describe the release as `unreleased` or `in progress`.

## Actual

Five current release-facing documents still referenced experimental.6 or an obsolete pre-release state after PR #19 was merged and its hosted verifier passed.

## Deterministic steps

From trusted Base `dd84c538624cdda4e65d7189821b43747c2c535f`, run:

```bash
rg -n 'release download v0\.2\.0-experimental\.6|agentic-sdd-governance-v0\.2\.0-experimental\.6\.bundle|experimental\.8.*\(unreleased\)|experimental\.8.*in progress' \
  README.zh-TW.md docs/USER_GUIDE.zh-TW.md RELEASE_NOTES.md CHANGELOG.md docs/ROADMAP.md
```

The Red command returns the stale current install targets and state markers recorded in the shareable terminal artifact.

## Environment and preconditions

Public repository clone on branch `docs/experimental8-release-metadata`; no credentials, user data, Production service, or network call is required for reproduction.
