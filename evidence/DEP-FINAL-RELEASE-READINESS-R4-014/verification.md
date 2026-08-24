# Verification

## Green command and result

At exact atomic implementation commit `f03af448f453859d02e63f501fc0ad9aa62ae5ac`:

- Focused hostile regression matrix: 17/17 PASS.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 229 tests completed without failure; 228 PASS and one sandbox-only AF_UNIX test SKIP.
- `sddgov validate .`, `sddgov ci verify .`, `sddgov doctor .`, and `sddgov ci local-gate .`: PASS; Repository Doctor verified 66 managed files.
- Wheel and sdist build: PASS. Wheel SHA-256 `e0c3b0da2b32f8860de9e293b564c1849086f85b58c7377aac239bfa6930562b`; sdist SHA-256 `aaa57de3b6250fe7db73d69aebb75c6e4b390d03a2d63bab018e787dc499ead8`.
- Fresh Python 3.12 environment installed all hash-locked dependencies and the built wheel; dependency check, Codex Doctor, Hermes Doctor, and offline synthetic Muse pilot all PASS. Both Doctors verified 66 managed files; the pilot reported `network_used=false` and `real_data_used=false`.
- Disposable rollback drill: `git revert --no-commit f03af448f453859d02e63f501fc0ad9aa62ae5ac` PASS; the resulting non-Evidence/non-audit tree exactly matched trusted Base `a5c27e306373829eee966222c3915f5a822b190c`. Reconciliation from the reverted source, Doctor, and the reverted 205-test suite all PASS with the same one sandbox-only skip.

## Before/after evidence

At reviewed Head `b815214632a820451d3e8444af9ebfea8a2ec0f5`, the eight focused Red assertions produced six failures and two errors spanning the five independent P1 contracts. The fixed candidate turns the expanded 17-test hostile matrix Green without adding an owner prompt or weakening L2/L3, Evidence, trusted-Base, or rollback gates.

## Remaining limitations

The AF_UNIX positive test cannot execute inside the local socket-restricted sandbox and must be rerun by the fresh independent Reviewer outside that restriction. GitHub security controls, a second exact-Head hosted verification, Merge, tag signing/attestation, downloaded-asset verification, and public Release remain separate external operations; none is claimed by this local proof.
