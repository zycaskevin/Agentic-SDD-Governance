# Verification

## Green command and result

PASS on exact implementation commit `8459285df7e9d6c20039e2e9a752d561390e3ae2`: 271 tests, 2 skipped, 0 failed; repository validation, CI Guard, Codex Doctor (71 managed files), and offline demo PASS. Build and twine PASS. Fresh-wheel smoke PASS with `source_checkout_imported=false`, exact offline bundle verification, Codex/Hermes Doctor at 71 files, and quick-demo PASS. Artifact SHA-256 values: wheel `100f84374439ebf555efebb48a2450c1b6daae7911191cc4533e899f205c9052`; sdist `2bb19c2a9fcd0dd91a1eab287a5d13ee8504c9faf880ebe4d4f1e431c2a57892`; aarch64 offline archive `432b63fe1b136a827c08a842d4e882e16cb5914abe4df01777bd3ca52fc6ae30`.

## Before/after evidence

RED is mapped by `terminal--coderabbit-pr25-inline.txt` and `terminal--coderabbit-pr25-review-meta.txt`, stored as text rather than JSON. GREEN is mapped by the implementation test, validation, package, bundle, fresh-wheel, and rollback artifacts. The rollback contract names Base commit `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. The disposable revert produced result tree `7b48daf1558a6ca3e02f20654663292a39772fce`, exactly equal to that Base commit's tree object `7b48daf1558a6ca3e02f20654663292a39772fce`; these are intentionally different Git object types and identifiers. After managed-resource reconciliation, the reverted source reported `0.2.0-experimental.8`, Doctor PASS, and 229 tests PASS with 2 environment skips.

## Remaining limitations

This local offline bundle proof covers only `linux-aarch64-py312`; it does not validate the release workflow's required `linux-x86_64-py312` bundle. The sealed R3 DEP on PR #25 is not rewritten: its invalid redacted JSON filename/content and ambiguous Base wording remain historical findings, while R4 uses new text Evidence and explicit object types. The first full review capture correctly failed redaction closed because untrusted review code contained an overlong incomplete private-key marker; that uncommitted attempt is preserved only in `/tmp/sddgov-r4-failed-redaction-backup`, and the tracked DEP uses a bounded title/URL derivative. No hosted trusted-Base run, exact-Head independent signed Review, Merge receipt, root Broker host rehearsal, GitHub release environment, TestPyPI/PyPI round trip, tag, or publication is claimed or authorized.
