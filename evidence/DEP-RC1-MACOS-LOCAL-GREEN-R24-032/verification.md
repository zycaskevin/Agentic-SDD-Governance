# Verification

## Green command and result

Targeted command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest tests.test_autonomy tests.test_broker tests.test_owner_approval` -> 147 tests OK with 4 expected skips.

Complete candidate-plus-Evidence command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q` -> 523 tests OK with 14 expected platform/sandbox skips. `sddgov validate .` and `sddgov ci verify .` also passed.

Configured Local Green ran in the externally bound canonical Owner repository with credentials cleared and real root-owned public trust metadata visible. It completed the full 523-test command with 5 expected skips, source validation, and `sddgov decision verify-product DEC-RC1-APPROVER-AUTHORITY-R22 work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json --path .`; all three commands returned zero. The decision result bound the active approver, repository, trust domain, request, current Owner-client identity, expiry, and receipt SHA-256 `fb01428e4f296be43639fc4494844d964619adc263ac42253fea1ff563806337`.

Rollback proof: from the Evidence-only child of product commit `d7360248f7d77f2cf363747f6222316448a818bb`, `git revert --no-commit` restored a non-audit tree byte-identical to trusted Base `92f4ba8388ecf1ef1f3407db6c49cef62f6ee196`. Reverted validation passed; the Base suite reported 237 tests OK with 1 expected skip; Codex setup reported the 66-file Base installation already current; Doctor reported no errors or warnings.

Package proof: an isolated release-tool environment built the candidate wheel and sdist without isolation, and Twine accepted both artifacts. The local build produced wheel SHA-256 `a631a4c10a43edef7dee89265952dd470529ca13cf9a227cd66970f8932a6b06` and sdist SHA-256 `150db428ea1746e1cdd3a57201c2abf055538830e614115513c3a958a0a6deb3`; archive hashes are rehearsal-specific, while the governed installed Owner-client source identity remains unchanged.

## Before/after evidence

Before: native macOS source Green stopped with 21 failures and 34 errors before packaging, while a local top-level gate and its complete-suite child waited on the same per-user lock. After: all fixture consumers share the product's exact fixed-alias canonicalization, hostile assertions execute at their intended boundaries, and the nested gate unit test uses a private lock namespace. Linux full and configured Local Green both complete without weakening production code.

## Remaining limitations

The superseding GitHub macOS/Ubuntu checks, CodeRabbit review, final Gate digest, and independent protected-file receipt remain outstanding. They must pass before merge; this Proof does not claim those future results.
