# L2 Decision Contract: Fixed Approver Authority Store

Decision ID: `DEC-RC1-APPROVER-AUTHORITY-R22`

## Exact scope

This decision authorizes the RC1 implementation to:

- retire and reject `SDDGOV_TRUSTED_APPROVERS_FILE` as a runtime authority-selection mechanism;
- use `/etc/sddgov/trusted-approvers.json` as the sole Linux and macOS runtime approver trust store;
- require the trust-store leaf to be a root-owned, single-linked regular file that is not writable by group or other;
- require every directory in the retained physical path chain to be root-owned, non-symlink, and not writable by group or other, after canonicalizing only macOS's fixed platform-owned `/etc` alias to `/private/etc`;
- fail closed when the Agent runs as root, the fixed store is absent or unreadable, the path generation changes, the document is malformed or oversized, or a legacy environment override is present; and
- document migration from an environment-selected external store to the fixed path without silently falling back to the legacy behavior;
- keep the Agent-side `sddgov` CLI non-signing while it validates and renders one exact A/B product-decision card; and
- provide a separate `sddgov-owner` terminal entry point that reconstructs assumptions, nonce, validity, and canonical receipt without private-key or signature arguments, asks only the uniquely matching externally held Ed25519 SSH-agent identity to sign, verifies the result against the fixed trust root, and writes a new owner-only receipt.

This decision does not authorize writing `/etc/sddgov`, provisioning a real Owner public key, installing or restarting a root service, or executing any Production operation. Those remain separate concrete Operational/L3 actions.

## Assumptions

- The runtime Agent is a non-root process on supported Linux or macOS hosts.
- On macOS, `/etc` is the supported logical authority location and the verifier maps only that fixed system alias to its physical `/private/etc` path; arbitrary caller symlinks remain forbidden.
- An operator provisions the fixed file outside the repository with readable least privilege, such as `root:sddgov 0640` or `root:wheel 0644`, and keeps its parent chain root-controlled.
- Existing deployments that set `SDDGOV_TRUSTED_APPROVERS_FILE` must remove that variable and migrate the same reviewed public trust records to the fixed path before using L2/L3 approval imports.
- Windows and hosts without a separate root-controlled identity remain fail-closed until a platform ACL or external control-plane contract is approved.
- Repository code, candidate CI, and Agent-controlled process environment are never an authority source.
- The Owner runs `sddgov-owner` from an independently installed reviewed artifact and an Owner-controlled terminal. The matching Ed25519 identity is unavailable to the Agent except through a provider that requires separate confirmation for each signature; an unconstrained Agent-accessible SSH key is a custody failure and is not supported authority.

## Options

- A — approve the fixed fail-closed authority contract and separated Owner approval client above.
- B — retain the trusted Base behavior in which a caller-selected environment variable names an external root-owned store.

Recommended: A. It removes caller-selected authority routing while preserving a documented migration and keeps actual privileged provisioning outside this code decision.

Reopen condition: `scope_or_assumptions_change`.
