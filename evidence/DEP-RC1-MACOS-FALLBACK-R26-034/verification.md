# Verification

## Green command and result

Focused workspace regressions passed: `test_fresh_smoke_workspace_falls_back_when_tmp_is_unavailable` and `test_fresh_smoke_canonicalizes_the_darwin_tmp_workspace` both returned Green.

Complete candidate-plus-Evidence verification ran 524 tests with 14 expected platform/sandbox skips and no failures. `sddgov validate .` and `sddgov ci verify .` passed.

Configured Local Green ran in the externally bound canonical Owner repository with general credentials cleared. It completed all 524 tests with 5 expected skips, source validation, and exact stored decision verification. The decision result verified approver `zycaskevin-agentic-sdd-governance-owner-2026q3`, repository, trust domain, unchanged request and Owner-client identity, expiry, and receipt SHA-256 `fb01428e4f296be43639fc4494844d964619adc263ac42253fea1ff563806337`.

An isolated release environment built the wheel and sdist without isolation; Twine accepted both. The wheel SHA-256 is `d2bdd7ed6d53fb667f64fb82a51794371201481804d0371f5fff04c70f2dc23d`; the sdist SHA-256 is `d5477561ec43347ba700c93a329befe851b5a44c0cc9ce07a06a6a9402d7aafd`. The offline release bundle contains ten hash-locked dependency wheels and four public assets. The unsandboxed fresh-wheel smoke passed with no source-checkout import, Owner client PASS, Codex and Hermes 73-file Doctor/validation, demo PASS, and native Linux Broker PASS.

Rollback proof reverted product commit `28a80236ba54d6b4ff17604ff3453a09c692047d` from its Evidence-only descendant. The non-audit tree was byte-identical to trusted Base `92f4ba8388ecf1ef1f3407db6c49cef62f6ee196`; Base validation passed; 237 Base tests passed with 1 expected skip; Codex setup reported 66 managed files already current; Doctor reported no errors or warnings.

## Before/after evidence

Red: R25 hosted macOS source Green had one fixture assertion failure before packaging. Green: R26 uses the same shared fixed-alias canonicalizer for the expected fixture representation.

## Remaining limitations

Hosted Ubuntu/macOS, CodeRabbit, independent review, and the final trusted-Base merge verification remain mandatory before merge. They are not claimed by this local Proof.
