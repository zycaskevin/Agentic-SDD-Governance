# Regression Evidence

## Regression test added or strengthened

The targeted experimental.7 command failed 15 checks. The same authority, CI, Evidence, governance, rollback, redaction, protected-path, dependency, and version tests now pass on the experimental.8 branch.

## Related tests executed

- Complete repository suite: 166/166 PASS in an unrestricted local process with the real Unix-socket case executed; the restricted sandbox independently reports 165 PASS and the expected single socket skip.
- `sddgov validate .`: PASS.
- `sddgov ci verify .`: PASS using parsed YAML semantics.
- Python 3.12-targeted hash lock: PASS. Fresh Python 3.11 installation with `--require-hashes`: PASS with `cryptography==50.0.0` and `typing-extensions`; 166/166 tests PASS. Fresh-wheel `pip check`: PASS.
- Concurrency regression: two simultaneous identical Operational Action requests persist one record and mark only one response as newly created.
- Exact `0.2.0.dev8` wheel/sdist archive-path inspection: PASS; fresh Codex/Hermes `setup-agent` plus `doctor`: PASS; offline synthetic Muse pilot: PASS without network or real data.

## Unaffected paths sampled

Installer upgrade/audit events, Reviewer and Merge signatures, L3 nonce semantics, full/portable DEP association checks, no-clobber attachment publication, benchmark fixture, and the synthetic Muse pilot test module remain Green. Independent review, hosted Base workflow, Merge, and Release remain separate gates and are not implied by this local Proof.
