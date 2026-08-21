# L3 Broker Operations and Readiness

The L3 Broker is a separately running, root-owned Unix service that atomically consumes an approval nonce once across clones and Agent sessions. It is not a signer and does not grant authority: SDG verifies the Owner signature, exact operation payload, runtime context, and expiry before asking the Broker to consume the nonce.

There is deliberately no production `--mock-broker`, alternate socket path, or repository-local ledger.

## Fixed control-plane paths

| Platform | Socket | Nonce ledger | Runtime context |
| --- | --- | --- | --- |
| Linux / WSL2 | `/run/sddgov/approval-broker.sock` | `/var/lib/sddgov/consumed-nonces.jsonl` | `/etc/sddgov/runtime-context.json` |
| macOS | `/private/var/db/sddgov/approval-broker.sock` | `/private/var/db/sddgov/consumed-nonces.jsonl` | `/etc/sddgov/runtime-context.json` |

The trusted approver store is also outside the repository and is selected by `SDDGOV_TRUSTED_APPROVERS_FILE`. All control-plane files are root-owned and not writable by group or other. The Agent process must be non-root.

## Readiness check

Run this from the same non-root account and environment that will run the Agent:

```bash
export SDDGOV_TRUSTED_APPROVERS_FILE=/etc/sddgov/trusted-approvers.json
sddgov broker doctor --path /absolute/path/to/repository
```

`READY` requires all five checks: supported platform, non-root Agent identity, valid root-owned runtime context, valid out-of-band Ed25519 public trust store, and the exact `READY` response from a trusted fixed-path socket. The health request does not create or consume a nonce.

The daemon validates or creates the owner-only ledger and fsyncs its directory before binding the socket. A malformed, linked, broadly writable, or unreadable ledger prevents service startup, so a running health endpoint cannot hide a deferred ledger-open failure.

`NOT_READY` is a hard block on real L3 operations. It is not permission to retry with a caller-selected context, a copied socket, or a repository-local trust file.

## Linux systemd installation

The repository provides `services/sddgov-broker.service`. Review and replace its `/opt/sddgov/venv/bin/sddgov` path with the independently installed, pinned wheel location.

1. Create a dedicated system group `sddgov` and add only approved Agent service accounts.
2. Install the pinned wheel under `/opt/sddgov/venv`; the Agent must not be able to modify that environment.
3. Create root-owned `/etc/sddgov/runtime-context.json` and `/etc/sddgov/trusted-approvers.json` with mode `0644` or stricter. The private key never goes on this host unless it is itself the approved external signer.
4. Install the reviewed unit as `/etc/systemd/system/sddgov-broker.service`, then enable and start it.
5. Start a new login session so group membership is refreshed, export the trust-store path, and run `broker doctor` as the non-root Agent user.

The systemd unit creates `/run/sddgov` and `/var/lib/sddgov` with bounded modes. Do not place either path on a shared volume.

## WSL2 checklist

- Enable systemd in `/etc/wsl.conf`, shut down the WSL distribution, and start it again before installing the unit.
- Keep socket, ledger, runtime context, trust store, and SDG environment inside the Linux filesystem, never `/mnt/c` or another DrvFS mount.
- Verify `id -u` is not `0`, `id -Gn` includes `sddgov`, and every parent of `/run/sddgov` is root-owned and not group/world-writable.
- Restart WSL and confirm the service returns, the ledger remains under `/var/lib/sddgov`, and an already consumed synthetic nonce remains rejected.

## macOS launchd installation

The repository provides `services/com.sddgov.broker.plist`. Review its binary path and `_sddgov` group before installation.

1. Create a dedicated `_sddgov` group and add only approved Agent accounts.
2. Create `/private/var/db/sddgov` as `root:_sddgov` mode `0750`; the ledger itself remains root-owned mode `0600`.
3. Create the root-owned runtime context and trusted approver store under `/etc/sddgov`.
4. Install the reviewed plist in `/Library/LaunchDaemons/com.sddgov.broker.plist` as `root:wheel` mode `0644`, then bootstrap it in the system launchd domain.
5. Start a new login session and run `broker doctor` from the non-root Agent account.

## Incident and restart behavior

- A duplicate nonce returns `ALREADY_CONSUMED`; the SDG client accepts only the exact `CONSUMED` response for a fresh operation.
- An invalid, oversized, extra-line, or malformed request returns `REJECTED` and does not modify the ledger.
- The append-only ledger is fsynced before `CONSUMED` is returned. Do not truncate, edit, replace, restore over, or delete it during ordinary operation.
- The service refuses to replace an existing socket path automatically. Inspect an unexpected or stale path as a security event before removal and restart.
- Back up the ledger according to audit retention rules. Restoring an older ledger can re-enable nonce replay and is forbidden.

Before sensitive-data adoption, rehearse service stop/start, host reboot, synthetic consumption, replay rejection, key revocation, and lost-key recovery. Record the results in a redacted DEP.
