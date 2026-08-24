# Regression Evidence

## Regression test added or strengthened

- Evidence control, raw, shareable, attachment, and new-DEP publications now verify complete generation snapshots through the outer root/path lease and roll back exact owned generations on any precommit failure.
- Post-publication wrapper failures for collect, redact, and transition now raise and restore predecessor state instead of returning false success.
- Predecessor finalization reconciles an unlink that linearized before its durability report failed.
- DEP-tree cleanup claims children with native no-clobber rename and preserves a later child generation.
- Regular-file and release writers cover partial writes, close-real-then-raise, directory fsync failure, near-name-limit cleanup, claim collisions, and later-writer replacement.
- Broker tests cover partial signal-handler setup and real AF_UNIX publication, health, cleanup, replacement preservation, and restart.
- Control-plane tests bound the authority document and retain/recheck the root-owned path; Darwin tests allow only fixed `/tmp`, `/var`, and `/etc` system aliases.
- Workflow and release tests require source import for TestPyPI byte equality and reject root/distribution asset-name collisions.
- The current-main integration preserves Issue #44's stricter fail-closed Draft-guard parser and Issue #46's release-note privacy boundary while advancing the candidate to RC1.
- Owner-approval tests require one duplicate-key-free repository-relative L2 request, exact ordered A/B semantics with only A approvable, a bounded real-PTY `/dev/tty` line and card without machine digests, no Agent-side signing command, and an Owner-only entry point with no private-key/signature/assumption/key-ID/validity overrides. The POSIX launcher enters Python isolated mode before package import, ignores hostile `PYTHONPATH`, requires a non-system-site venv, and verifies its bytes, unique installed distribution, canonical wheel RECORD including an explicit launcher SHA-256, exact entry-point contract, protected modes, and current installed source through call-wide snapshots. Dynamic-loader, complete-venv, and signer-channel isolation remain explicit Owner-custody preconditions established before the kernel starts the shell launcher; runtime checks are diagnostics, and generic SSH confirmation is not claimed as semantic approval. Tests also cover terminal-control rejection in arguments/version/card fields, duplicate/alias metadata rejection, unique external-key matching, signature re-verification, B/refusal without signer contact, same-inode and between-file input mutation rejection, fixed repository/trust-domain audience verification, one signed request artifact, and no-follow public receipt output. New or reused receipts must have the exact displayed validity window, Owner ownership, one link, exact `0640` mode, and the pre-provisioned `2750` setgid outbox group; strict umask cannot silently make the handoff private, and no repeat signing occurs after an exact commit.
- `sddgov decision verify-product` revalidates the stored row against the Ed25519 envelope, exact request scope and assumption paths, active key, fixed audience sidecar, expiry, validity policy, signed Owner-client binding, and current installed-client identity. The exact command is part of repository Local Green; inserting a schema-shaped local row cannot satisfy this path.

## Related tests executed

- Current Owner approval, autonomy, and shared filesystem suite: 117 tests executed; 116 passed and 1 sandbox AF_UNIX test skipped.
- Current full source suite: 513 tests executed; 498 passed, 14 platform/sandbox tests skipped, and one repository-contract failure remains intentionally Red until the Owner-signed L2 decision is imported and `verify-product` succeeds.
- Focused Evidence preview suite: 77 tests passed, 1 Darwin-only skip.
- Focused Broker preview suite: 39 tests passed, 3 superseded native-test skips.
- Native Linux AF_UNIX preview suite: 9 tests passed, 1 installed-wheel provenance skip covered by the predecessor fresh-wheel smoke.
- Repository `validate`: PASS.
- CI contract `verify`: PASS.
- The current exact preview passed wheel/sdist build, Twine metadata, and the hash-locked offline bundle after the final source corrections. The predecessor preview's fresh installed-wheel smoke imported no source-checkout code, verified the isolated Owner launcher against hostile `PYTHONPATH`, passed both adapter Doctors with 73 managed files each, passed the quick demo, and passed the native Linux Broker rehearsal. Exact current installed-wheel and hosted proof are deliberately left to the independent reviewer and CI; the Main Agent did not execute the Owner entry point.

## Unaffected paths sampled

- Canonical, managed, packaged, and installed governance resource parity.
- Both Codex and Hermes adapter installation/Doctor paths.
- Existing rollback verifier, merge-gate, redaction, CI cost guard, installer, and synthetic pilot suites.
- No external publication, root filesystem write, service install, or Production operation was performed.
