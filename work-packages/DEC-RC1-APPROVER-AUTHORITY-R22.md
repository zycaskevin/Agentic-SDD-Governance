# L2 Decision Contract: Fixed Approver Authority Store

Decision ID: `DEC-RC1-APPROVER-AUTHORITY-R22`

Owner client binding: {"source_sha256":"d3380ae822602cf1242283f736046c87de14f3daf4186fb2688f0cddae0bf7f1","version":"0.2.0rc1"}

## Exact scope

This decision authorizes the RC1 implementation to:

- bind every product receipt reuse to repository `github.com/zycaskevin/agentic-sdd-governance` and trust domain `agentic-sdd-governance-owner-2026q3`;
- retire and reject `SDDGOV_TRUSTED_APPROVERS_FILE` as a runtime authority-selection mechanism;
- use `/etc/sddgov/trusted-approvers.json` as the sole Linux and macOS runtime approver trust store;
- keep the signed product receipt compatible with the trusted Base schema while requiring the separate fixed, root-controlled `/etc/sddgov/trusted-approver-domains.json` sidecar to bind each Owner key ID to exactly one canonical GitHub repository, one exact host-local repository root, and one trust domain;
- require the trust-store leaf to be a root-owned, single-linked regular file that is not writable by group or other;
- require every directory in the retained physical path chain to be root-owned, non-symlink, and not writable by group or other, after canonicalizing only macOS's fixed platform-owned `/etc` alias to `/private/etc`;
- fail closed when the Agent runs as root, the fixed store is absent or unreadable, the path generation changes, the document is malformed or oversized, or a legacy environment override is present; and
- document migration from an environment-selected external store to the fixed path without silently falling back to the legacy behavior;
- keep the Agent-side `sddgov` CLI non-signing while it validates and renders one exact A/B product-decision card; and
- provide a separate `sddgov-owner` terminal entry point that reconstructs the exact request-backed assumptions, nonce, validity, and canonical receipt without private-key or signature arguments, asks only the uniquely matching externally held Ed25519 identity to sign, verifies the result against the fixed trust root, and writes a public `0640` receipt into a pre-provisioned Owner-write-only/Agent-read-only outbox.

This decision does not authorize writing `/etc/sddgov`, provisioning a real Owner public key, installing or restarting a root service, or executing any Production operation. Those remain separate concrete Operational/L3 actions.

## Assumptions

- The runtime Agent is a non-root process on supported Linux or macOS hosts.
- On macOS, `/etc` is the supported logical authority location and the verifier maps only that fixed system alias to its physical `/private/etc` path; arbitrary caller symlinks remain forbidden.
- An operator provisions both fixed control-plane files outside the repository with readable least privilege, such as `root:sddgov 0640` or `root:wheel 0644`, and keeps their parent chain root-controlled.
- Existing deployments that set `SDDGOV_TRUSTED_APPROVERS_FILE` must remove that variable and migrate the same reviewed public trust records to the fixed path before using L2/L3 approval imports.
- Windows and hosts without a separate root-controlled identity remain fail-closed until a platform ACL or external control-plane contract is approved.
- Repository code, candidate CI, and Agent-controlled process environment are never an authority source.
- The exact host-local repository root is chosen and written only during the separate privileged provisioning action; a candidate-controlled Git remote alone is never repository authority.
- The exact request JSON is itself one signed assumption artifact; its A/B descriptions, explanation, verified facts, impact, scope, signer policy, validity, and remaining assumption paths therefore reopen the decision when changed.
- The Owner runs `sddgov-owner` from an independently installed reviewed artifact and an Owner-controlled foreground terminal. Before any interpreter or package import, the complete venv, launcher, installed source, metadata, `pyvenv.cfg`, and relevant parent directories are controlled by an identity the Agent cannot modify. Runtime mode, RECORD, site, and environment checks are diagnostics, not proof of pre-execution isolation.
- The matching Ed25519 identity and signer socket/channel are inaccessible to the Agent operating-system identity and processes. Generic SSH confirmation alone is not semantic card binding: the Owner initiates the isolated client and rejects every unexpected prompt, or an external signer independently displays and binds the exact card/receipt and caller.
- A pre-provisioned Owner-owned setgid outbox allows the Agent handoff group to read and traverse but not write; the public receipt is mode `0640`. This one-way channel avoids chat relay without broadening access to the Owner venv or signer.
- The Owner-controlled device or process supervisor establishes a clean dynamic-loader and non-system-site environment before the kernel starts the POSIX launcher. The launcher's `LD_*`/`DYLD_*` and venv checks are fail-closed diagnostics only and are not evidence that code could not run before the first script line.

## Options

- A — approve the fixed fail-closed authority contract and separated Owner approval client above.
- B — retain the trusted Base behavior in which a caller-selected environment variable names an external root-owned store.

Recommended: A. It removes caller-selected authority routing while preserving a documented migration and keeps actual privileged provisioning outside this code decision.

Reopen condition: `scope_or_assumptions_change`.
