# Verification

## Green command and result

PASS on exact implementation commit `05822d004e84c13d4e5bc6e3967e798b675348ed`: 278 tests, 2 skipped, 0 failed; source validation, CI Guard, Doctor with 71 managed files, source-checkout demo, and Local Green passed. Build and twine passed. Fresh-wheel smoke passed with `source_checkout_imported=false`, exact offline bundle verification, and Codex/Hermes setup, Doctor, installed managed-tree validation, and quick pilot. SHA-256 values: wheel `e81ac551ad3474a0dfc81b58970ff026c9639189b6eda1d630671412c3872b38`; sdist `363054a48a5393d1e42de20b02e0aa838c9656a245a7a4f69a9a1cbd5d17e59e`; aarch64 offline archive `1595ba7ad665f79f227e50869be06e314ddaa5e2ac89a348a018b2b27b83049c`.

## Before/after evidence

RED is preserved in `terminal--r5-red.txt`; exact PR 25 and PR 26 review nodes and all 19 authoritative inline URLs are preserved in `terminal--upstream-review-binding.txt`; GREEN and limitations are in `terminal--r5-green.txt`; and the disposable rollback is in `terminal--rollback-proof.txt`. The implementation tree is `a45f863785de71d6af39705401b482b9ec4e6aab`. Reverting it produced `7b48daf1558a6ca3e02f20654663292a39772fce`, exactly equal to the declared Base tree; experimental.8 Doctor and 229 tests passed with 2 environment skips.

## Remaining limitations

Local package proof is `linux-aarch64-py312`, not the publish workflow's required `linux-x86_64-py312`. The execution sandbox forbids native Unix socket creation, so two environment-specific tests remain skipped; the socket mode regression exercises the real portable path chmod with controlled socket metadata, but no root service rehearsal is claimed. Local CodeRabbit CLI 0.7.5 remained unauthenticated and its login failed with `Failed to start server. Is port 0 in use?`; the completed GitHub App review is the upstream review Evidence. No exact-Head independent signed Review receipt, root Broker install, GitHub environment/ruleset, RC tag, GitHub Release, TestPyPI/PyPI round trip, attestation, or publication exists or is claimed.
