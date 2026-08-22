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
- Owner-approval tests require one validated repository-relative L2 request, exact ordered A/B semantics, a concise `/dev/tty` card without machine digests, no Agent-side signing command, an Owner-only entry point with no private-key/signature/assumption/key-ID/validity overrides, terminal-control rejection, unique external-key matching, signature re-verification, refusal without signer contact, same-inode input mutation rejection, a reviewed installed-source digest bound exactly once inside the signed assumption artifact, fixed repository/trust-domain audience verification, and no-follow `0600` receipt output with parent-generation revalidation.
- `sddgov decision verify-product` revalidates the stored row against the Ed25519 envelope, exact request scope and assumption paths, active key, fixed audience sidecar, expiry, validity policy, and signed Owner-client binding; inserting a schema-shaped local row cannot satisfy this path.

## Related tests executed

- Current Owner approval, autonomy, and shared filesystem suite: 94 tests executed; 93 passed and 1 sandbox AF_UNIX test skipped.
- Current full source suite: 487 tests executed; 472 passed, 14 platform/sandbox tests skipped, and one repository-contract failure remains intentionally Red until the Owner-signed L2 decision is imported and `verify-product` succeeds.
- Focused Evidence preview suite: 77 tests passed, 1 Darwin-only skip.
- Focused Broker preview suite: 39 tests passed, 3 superseded native-test skips.
- Native Linux AF_UNIX preview suite: 9 tests passed, 1 installed-wheel provenance skip covered by the predecessor fresh-wheel smoke.
- Repository `validate`: PASS.
- CI contract `verify`: PASS.
- The predecessor R22 preview passed wheel/sdist build, Twine metadata, the offline bundle, and fresh installed-wheel smoke. Because the Owner-client source digest changed during this correction, those package proofs must be regenerated for the future exact reviewed revision before Green/Proof.

## Unaffected paths sampled

- Canonical, managed, packaged, and installed governance resource parity.
- Both Codex and Hermes adapter installation/Doctor paths.
- Existing rollback verifier, merge-gate, redaction, CI cost guard, installer, and synthetic pilot suites.
- No external publication, root filesystem write, service install, or Production operation was performed.
