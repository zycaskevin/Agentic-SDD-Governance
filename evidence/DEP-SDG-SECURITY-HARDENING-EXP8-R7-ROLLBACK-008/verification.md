# Verification

## Green command and result

PASS at Evidence-bound Head `adcba02`: `198 passed, 144 subtests passed`; `sddgov validate` and `sddgov ci verify` PASS; all eight experimental.8 DEPs pass full and portable strict verification. The permanent applicability probe accepts atomic implementation commit `822ed753ff87d8eed2e3256cf8ae30b2a125e3c4` and rejects the historical overlapping boundary. Wheel and sdist build PASS; wheel SHA-256 is `01e76a6db82ada8f66598917c9258b59714152f5b9d9a1eb0039434071f7fb7a`, sdist SHA-256 is `f909851ac18bb1a188f0c061a7168a935861a7e7e260385b3b8d44493819812a`, and the wheel contains 93 members. A fresh wheel install passed `pip check`, Codex/Hermes doctor with 63 managed files each, and the offline synthetic Muse pilot with `network_used=false` and `real_data_used=false`.

## Before/after evidence

RED: selected `d7e16f2...` returned four conflicts. GREEN: a Repo-external disposable clone ran `git revert --no-commit 822ed753ff87d8eed2e3256cf8ae30b2a125e3c4` without conflict, and the reverted non-Evidence/non-audit tree exactly matched the trusted Base. The isolated `merge-tree` result also matched the Base and the hostile union/custom-driver tests passed.

## Remaining limitations

The trusted experimental.7 Base cannot run the new applicability check itself; this bootstrap PR therefore still requires another fresh independent review of the exact final candidate before signing. No Hosted verification, Merge, or Release is authorized by this local Proof.
