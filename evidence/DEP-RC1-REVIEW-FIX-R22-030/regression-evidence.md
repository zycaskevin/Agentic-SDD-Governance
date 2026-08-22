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
- Owner-approval tests require one validated repository-relative L2 request, a concise card without machine digests, no Agent-side signing command, an Owner-only entry point with no private-key/signature arguments, unique external-key matching, signature re-verification, refusal without signer contact, same-inode input mutation rejection, and no-follow `0600` receipt output.

## Related tests executed

- Focused Evidence suite: 77 tests passed, 1 Darwin-only skip.
- Focused Broker suite: 39 tests passed, 3 superseded native-test skips.
- Native Linux AF_UNIX suite: 9 tests passed, 1 installed-wheel provenance skip covered by fresh-wheel smoke.
- Full source suite: 460 tests executed; 445 passed, 14 platform/sandbox tests skipped, and one repository-contract failure remains intentionally Red until the Owner-signed L2 decision is imported.
- Repository `validate`: PASS.
- CI contract `verify`: PASS.
- Wheel and sdist build plus Twine metadata: PASS.
- Offline bundle: PASS with 10 dependency wheels and 4 public assets.
- Fresh installed-wheel smoke: PASS; no source-checkout import, 13 bundle files/12 payload files, Codex and Hermes Doctor each validated 71 managed files, demo PASS, installed Broker native health PASS.

## Unaffected paths sampled

- Canonical, managed, packaged, and installed governance resource parity.
- Both Codex and Hermes adapter installation/Doctor paths.
- Existing rollback verifier, merge-gate, redaction, CI cost guard, installer, and synthetic pilot suites.
- No external publication, root filesystem write, service install, or Production operation was performed.
