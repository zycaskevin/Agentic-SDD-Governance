# Verification

## Green command and result

Focused command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest tests.test_owner_approval tests.test_autonomy tests.test_fs_security -q` -> 122 tests, 121 pass, 1 expected sandbox skip.

Full command after the signed decision import: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v` -> 523 tests, 509 pass, 14 expected platform/sandbox skips, and no failures.

The configured Local Green ran from a credential-cleared non-root environment with the real root-owned control-plane metadata visible and passed all three configured commands: the complete suite, `sddgov validate .`, and exact `sddgov decision verify-product DEC-RC1-APPROVER-AUTHORITY-R22 work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json --path .`.

Trusted-Base compatibility: exact Base `92f4ba8388ecf1ef1f3407db6c49cef62f6ee196` accepted the R23 DEP in portable-strict mode after the manifest was pinned to Base-compatible schema `1.0`. Its static rollback verifier accepted final product commit `2c1f6d6f3a73e77cfc7d563ed4e20a1a3e2ad9b1`. A separate full clone reverted that commit at the Evidence Head; the result was byte-identical to Base outside Evidence/gate/review paths, Base validation passed, and the Base suite reported 237 tests OK with 1 expected skip.

Package verification: a clean no-system-site-packages Python 3.12 venv installed the rebuilt wheel entirely from the locked offline wheelhouse; `pip check` reported no broken requirements. The installed package imported from that venv outside the source checkout and reported Owner-client source identity `ac944efc040cbc103cd1664ebbd365378539f66011a92613b1c2200ef1ead826`, exactly matching the governed request and source tree. Twine accepted both wheel and sdist. A fresh build from the sealed implementation-plus-Evidence topology produced wheel SHA-256 `033813e143290872ca18cf68ec0b319c0589c852c28ed1cd61a95a2b3439072c` and sdist SHA-256 `3bb489088b74a91720bda210912c7a338f1b9add4fdb9303851aeb4af0aecff9`; installed source identity, rather than archive timestamps, is the governed Owner-client binding.

## Before/after evidence

Before: the root Owner runtime reached card construction and deterministically failed at the trusted-key stage without signer or outbox access. After: route, fixed-path, non-root rejection, poisoned-Agent-loader sign/final verification, and existing-receipt reuse regressions pass; Agent root refusal is unchanged. The independently reviewed root-only installer and non-signing diagnostic returned `OWNER_R23_INSTALL_AND_DIAGNOSTIC_PASS`. The Owner then selected canonical Option A through the isolated terminal client. Non-root import verified the Ed25519 envelope, active key, exact assumptions, repository audience, trust domain, validity, and current Owner-client identity. Stored-decision re-verification returned `SIGNATURE_ROW_AUDIENCE_AND_REQUEST_VERIFIED`, receipt SHA-256 `fb01428e4f296be43639fc4494844d964619adc263ac42253fea1ff563806337`, expiring `2026-09-22T15:55:57Z`.

## Remaining limitations

Hosted checks, CodeRabbit, Gate construction, and the final independent protected-file receipt remain outstanding. The Main Agent did not execute `sddgov-owner`, answer the Owner prompt, or access private key material.
