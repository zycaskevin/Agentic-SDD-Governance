# Verification

## Green command and result

- Exact implementation commit `a4ae82a3fdaf494f102c9ca1f6386f59a3c93cdc`
  was checked out in a disposable clone.
- `PYTHONPATH=src python -m unittest discover -s tests -v`: 263 passed,
  two environment-only skips.
- `sddgov validate .`, `sddgov ci verify .`, `sddgov doctor .`, and the offline
  Quick Demo: PASS. Doctor reports rc1 and 71 managed files.
- Wheel and sdist build plus Twine: PASS. Wheel SHA-256
  `d37aee811e732bd63a50597fdb659850eb17b7daf7963575d349686091696fdd`;
  sdist SHA-256
  `6bef9242d668e99a4e4b19a8a8f2201f8b68e18b263d9b8deb8e0bb6df25e947`.
- Hash-locked offline bundle and fresh-wheel smoke: PASS. Archive SHA-256
  `44d7984d3cab728fb538caf84ec7d32fefc7f369aace3ea9e48655538fb80635`;
  10 dependency wheels, 12 bundle files, no source-checkout import, Codex and
  Hermes Doctor 71, Quick Demo PASS, and no real data.
- Package provenance timestamps: sdist built
  `2026-08-21T13:14:17.468421517Z`, wheel built
  `2026-08-21T13:14:17.746421208Z`, and the consolidated package record was
  captured `2026-08-21T13:15:22Z`.
- Disposable rollback restored exact Base tree
  `7b48daf1558a6ca3e02f20654663292a39772fce`, Doctor experimental.8 with
  66 managed files, and all 229 Base tests with two environment-only skips.

## Before/after evidence

- Before: CodeRabbit Run `73e9b5da-9a00-449e-b784-285ee081063c` completed with
  18 findings against R2 Head `f7dc73c...`.
- After: the release credential exists only in the three exact-tag protected
  jobs; CI Guard validates exact write exceptions; Broker partial reads and
  post-bind failure tests pass; nested FAIL and cross-line PEM regressions pass;
  installation documentation selects one py312 bundle and one consistent CLI.

## Verified artifact mapping

- `terminal--coderabbit-r2-review.json`: Red/Evidence review input, locally
  redacted before publication.
- `terminal--source-validation.log`: Green and Proof for repository validation
  plus CI Cost Guard; both return `ok: true`.
- `terminal--full-tests.log`: Green regression matrix for the immutable R3
  implementation commit.
- `terminal--doctor-demo.log`: Green installed-governance parity and end-user
  Quick Demo behavior.
- `terminal--distribution.log`, `terminal--release-bundle.json`,
  `terminal--fresh-wheel-smoke.json`, and `terminal--package-build-record.log`:
  Proof for package build, Twine, offline inventory, fresh install, timestamps,
  and source-checkout exclusion.
- `terminal--rollback-drill.log`: Proof that the single implementation revert
  restores exact Base plus its Doctor and test baseline.

## Remaining limitations

- Independent protected-file signature, GitHub environments, exact tag,
  TestPyPI/PyPI round trip, root Broker hosts, WSL2/macOS, and external release
  publication remain separate gates and are not claimed by Local Green.
