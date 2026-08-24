# Verification

## Green command and result

Focused workspace regressions: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest tests.test_release_bundle.ReleaseBundleTests.test_fresh_smoke_canonicalizes_the_darwin_tmp_workspace tests.test_release_bundle.ReleaseBundleTests.test_fresh_smoke_workspace_falls_back_when_tmp_is_unavailable -v` -> 2 tests PASS.

Complete candidate-plus-Evidence command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q` -> 524 tests PASS with 14 expected platform/sandbox skips. `sddgov validate .` and `sddgov ci verify .` passed.

Configured Local Green ran in the externally bound canonical Owner repository with credentials cleared and real root-owned public trust metadata visible. It completed the full 524-test command with 5 expected skips, source validation, and `sddgov decision verify-product DEC-RC1-APPROVER-AUTHORITY-R22 work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json --path .`; all three commands returned zero. The decision result verified the active approver, repository, trust domain, request, unchanged Owner-client identity, expiry, and receipt SHA-256 `fb01428e4f296be43639fc4494844d964619adc263ac42253fea1ff563806337`.

Package proof: an isolated release-tool environment built the candidate wheel and sdist without isolation; Twine accepted both. The wheel SHA-256 is `9396e7f5091fc48cf837bfe89ad7403ef2076cec049dca5f65bb245b991429bb`; the sdist SHA-256 is `2f01ed6bb5d9361dc3ecc8cf732f453d8a9e8f00a8bf042e850eb198d71e3dc0`. The offline release bundle contains ten hash-locked dependency wheels and four public assets. The unsandboxed fresh-wheel smoke passed without source-checkout imports, including Owner client, Codex/Hermes 73-file Doctor/validation, demo, and native Linux Broker checks.

Rollback proof: from the Evidence-only child of product commit `eb1bdae60838135cddf697ab43885229df2cb64c`, `git revert --no-commit` restored a non-audit tree byte-identical to trusted Base `92f4ba8388ecf1ef1f3407db6c49cef62f6ee196`. Reverted validation passed; the Base suite reported 237 tests PASS with 1 expected skip; Codex setup reported the 66-file Base installation already current; Doctor reported no errors or warnings.

Superseding hosted Linux/macOS, CodeRabbit, final Gate, and independent-review results remain outstanding. They must pass before merge and are not claimed by this local Proof.

## Before/after evidence

Before: macOS used two fixed spellings of one temporary venv and the installed Owner topology probe failed after every earlier job stage had passed. After the focused fix, the harness canonicalizes once before it derives the venv, launcher, bundle, report, and socket paths; the production Owner runtime is unchanged.

## Remaining limitations

The superseding GitHub checks, final digest, CodeRabbit review, and independent protected-file receipt remain outstanding. This current Evidence phase does not claim those future results.
