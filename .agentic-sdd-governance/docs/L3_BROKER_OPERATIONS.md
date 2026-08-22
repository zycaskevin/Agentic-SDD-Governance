# L3 Broker Operations and Readiness

The L3 Broker is a separately running, root-owned Unix service that atomically consumes an approval nonce once across clones and Agent sessions. It is not a signer and does not grant authority: SDG verifies the Owner signature, exact operation payload, runtime context, and expiry before asking the Broker to consume the nonce.

There is deliberately no production `--mock-broker`, alternate socket path, or repository-local ledger.

## Fixed control-plane paths

| Platform | Socket | Nonce ledger | Runtime context |
| --- | --- | --- | --- |
| Linux / WSL2 | `/run/sddgov/approval-broker.sock` | `/var/lib/sddgov/consumed-nonces.jsonl` | `/etc/sddgov/runtime-context.json` |
| macOS | `/private/var/db/sddgov/approval-broker.sock` | `/private/var/db/sddgov/consumed-nonces.jsonl` | `/etc/sddgov/runtime-context.json` |

The trusted approver store is outside the repository and its authority path is fixed at `/etc/sddgov/trusted-approvers.json`; an `SDDGOV_TRUSTED_APPROVERS_FILE` caller override fails closed instead of selecting authority. All persistent control-plane files—the ledger, runtime context, and trust store—are root-owned and not writable by group or other. The Unix socket must be root-owned with exact mode `0660` and the fixed dedicated socket group (`sddgov` on Linux/WSL2, `_sddgov` on macOS) so approved non-root Agent service accounts can connect. A different group or any broader/narrower mode is `NOT_READY`. The Agent process must be non-root.

## Readiness check

Run this from the same non-root account and environment that will run the Agent:

```bash
unset SDDGOV_TRUSTED_APPROVERS_FILE
sddgov broker doctor --path /absolute/path/to/repository
```

`READY` requires all five checks: supported platform, non-root Agent identity, valid root-owned runtime context, valid out-of-band Ed25519 public trust store, and the exact `READY` response from a trusted fixed-path socket. The health request does not create or consume a nonce.

The daemon validates or creates the owner-only ledger and fsyncs its parent directory when the ledger is first created. An existing ledger is opened and fully validated before the socket is bound. A malformed, linked, broadly writable, or unreadable ledger prevents service startup, so a running health endpoint cannot hide a deferred ledger-open failure.

Socket publication is descriptor-anchored. The Broker binds an unpredictable pathname inside `.broker-staging`, a root-owned mode `0700` directory below the fixed socket parent, captures that pathname's filesystem identity, applies the final access mode, and then publishes it with the platform's native atomic no-clobber primitive (`renameat2(..., RENAME_NOREPLACE)` on Linux or `renameatx_np(..., RENAME_EXCL)` on macOS). It never compares the socket descriptor inode with the pathname inode because those are distinct kernel objects. If the first staging-path stat fails, only the exclusive staging entry is removed through the already-open directory descriptor; the fixed final path is untouched. After publication, shutdown removes the final path only while its captured pathname identity still matches, so a replacement is preserved. If the no-clobber primitive is unavailable, the final path already exists, or the complete native AF_UNIX staging pathname exceeds the platform limit, startup fails closed. Native tests use a deliberately short owner-only temporary root so Darwin exercises these publication semantics within its `sun_path` boundary; the fixed production staging path is also tested against that boundary.

The daemon is deliberately single-request-at-a-time. Each connection may send
one newline-terminated record of at most 2048 bytes within a two-second monotonic
read deadline; malformed, partial, extra-line, oversized, or late input receives
`REJECTED` without a ledger write. The reply uses a new independent two-second
send deadline, so a trickling or disconnected client cannot consume the next
request's service window.

`NOT_READY` is a hard block on real L3 operations. It is not permission to retry with a caller-selected context, a copied socket, or a repository-local trust file.

## Linux systemd installation

The repository provides `services/sddgov-broker.service`. Review and replace its `/opt/sddgov/venv/bin/sddgov` path with the independently installed, pinned wheel location.

1. Create a dedicated system group `sddgov` and add only approved Agent service accounts. The unit's `Group=` value must remain identical to the `--socket-group` value: the staging bind already has the final group, the Broker skips an unnecessary `chown` before atomic publication, and the empty capability set may safely omit `CAP_CHOWN`.
2. Install the pinned wheel under `/opt/sddgov/venv`; the Agent must not be able to modify that environment.
3. Create root-owned `/etc/sddgov/runtime-context.json` and `/etc/sddgov/trusted-approvers.json` with mode `0644` or stricter. The private key never goes on this host unless it is itself the approved external signer.
4. Install the reviewed unit as `/etc/systemd/system/sddgov-broker.service`, then enable and start it.
5. Start a new login session so group membership is refreshed, ensure the retired trust-store environment override is unset, and run `broker doctor` as the non-root Agent user.

The systemd unit creates `/run/sddgov` and `/var/lib/sddgov` with bounded modes. Do not place either path on a shared volume.

The supplied unit intentionally omits `SystemCallFilter=@system-service`. Add it only after a root-owned target-host rehearsal proves Broker startup, health, and nonce consumption with the exact deployed Python and cryptography runtime; retain the omission if any required syscall is blocked.

## WSL2 checklist

- Enable systemd in `/etc/wsl.conf`, shut down the WSL distribution, and start it again before installing the unit.
- Keep socket, ledger, runtime context, trust store, and SDG environment inside the Linux filesystem, never `/mnt/c` or another DrvFS mount.
- Verify `id -u` is not `0`, `id -Gn` includes `sddgov`, and every parent of `/run/sddgov` is root-owned and not group/world-writable.
- Restart WSL and confirm the service returns, the ledger remains under `/var/lib/sddgov`, and an already consumed synthetic nonce remains rejected.

## macOS launchd installation

The repository provides `services/com.sddgov.broker.plist`. The plist runs as `root:_sddgov` and applies decimal `Umask` 7 (octal `0007`). On macOS, Broker operational warnings go directly to the unified system log instead of a launchd-opened pathname, so retention is owned by the host logging policy and does not depend on fragile pathname rotation or SIGHUP reopening.

1. Create a dedicated `_sddgov` group and add only approved Agent accounts.
2. Create `/private/var/db/sddgov` as `root:_sddgov` mode `0750`; the ledger itself remains root-owned mode `0600`.
3. Create the root-owned runtime context and fixed trusted approver store under `/etc/sddgov`.
4. Install the pinned wheel into the root-owned environment, then require `test -x /opt/sddgov/venv/bin/sddgov` and `/opt/sddgov/venv/bin/sddgov --version` to pass before installing or bootstrapping the plist. A different installation path requires an independently reviewed plist with that exact absolute executable.
5. Confirm the host unified-log retention and export policy is bounded and appropriate for security operations. Broker logs only capacity warnings, rejected-request error classes, and listener failures; it never logs request bytes, nonces, receipt or payload digests, and it emits no per-request success or duplicate-consumption record.
6. Install the reviewed plist in `/Library/LaunchDaemons/com.sddgov.broker.plist` as `root:wheel` mode `0644`, validate it with `plutil -lint`, and only then bootstrap it in the system launchd domain.
7. Start a new login session, unset the retired trust-store environment override, and run `broker doctor` from the non-root Agent account. Confirm `log show --last 5m --predicate 'process == "sddgov" OR eventMessage CONTAINS "sddgov-broker"'` exposes operational warnings to the approved administrator account without request material.

launchd does not create `/private/var/db/sddgov` for this job; step 2 is therefore a mandatory preflight, not an optional hardening step. After `SIGKILL`, a host crash, or another unclean exit, `KeepAlive` may encounter the deliberately preserved socket pathname and repeatedly fail closed. The supplied plist sets `ThrottleInterval` to 30 seconds so this failure mode cannot form a tight restart loop. Unload the job first, record the exact pathname metadata and process/listener inspection, and remove `/private/var/db/sddgov/approval-broker.sock` only when it is a root-owned Unix socket with no live Broker. Never put wildcard deletion or unconditional stale-socket removal in the plist. Then bootstrap the job and re-run `broker doctor`.

## Ledger capacity and controlled epoch rollover

The active ledger is scanned on each consume request. SDG enforces a 64 MiB active-epoch capacity limit before allocating the nonce set or appending a record; reaching it fails health and consumption closed with a controlled-rollover diagnostic. Broker startup emits a capacity warning at 80% without weakening the hard limit. Monitor that warning, byte size, record count, and Broker latency well below the ceiling. Ordinary operation never truncates, compacts, restores over, or automatically rotates the ledger. When an operational threshold is reached, stop issuing L3 receipts and wait until every receipt issued in the current ledger epoch has expired; SDG permits at most 24 hours, and the runbook must also include the organization's positive clock-safety interval. If complete expiry and trustworthy clocks cannot be proven, do not roll the ledger.

With the Broker stopped, validate and preserve the old ledger as a root-owned, immutable audit archive, move it to a unique same-filesystem epoch name under change control, fsync the directory, and let the Broker create a new owner-only ledger. Record the old ledger digest, final record count, last receipt issuance time, expiry calculation, archive path, new epoch start, and readiness result. Never restore an archived or older epoch as the active ledger. This bounds active scan memory and latency without treating archive deletion as replay protection; receipt signature, exact payload, runtime context, and expiry checks remain mandatory before Broker consumption.

## Incident and restart behavior

- A duplicate nonce returns `ALREADY_CONSUMED`; the SDG client accepts only the exact `CONSUMED` response for a fresh operation.
- An invalid, oversized, extra-line, or malformed request returns `REJECTED` and does not modify the ledger.
- The append-only ledger is fsynced before `CONSUMED` is returned. Do not truncate, edit, replace, restore over, or delete it during ordinary operation.
- The service refuses to replace an existing socket path automatically. Inspect an unexpected or stale path as a security event before removal and restart.
- Back up the ledger according to audit retention rules. Restoring an older ledger can re-enable nonce replay and is forbidden.

Before sensitive-data adoption, rehearse service stop/start, host reboot, synthetic consumption, replay rejection, key revocation, and lost-key recovery. Record the results in a redacted DEP.

The Broker request loop is deliberately single-threaded with a `listen(32)` queue. A client can occupy that serial slot for the two-second read deadline and another two-second send deadline, delaying other approved `_sddgov`/`sddgov` members by roughly four seconds per connection. Clients must call `shutdown(SHUT_WR)` after sending their newline-terminated request so the Broker observes EOF promptly. Monitor connection rate, per-request service time, listener failures, repeated `REJECTED` counts, and ledger utilization; a rising service time with a healthy listener distinguishes a slow or stuck client from a genuine outage. Stop the offending client, confirm Broker health, and restart only through the inspected stale-socket procedure above. Rejected-request telemetry is limited to its safe error class and must never include request bytes, nonces, or digests. Scale-out or concurrency changes require a new replay-safety and ledger-locking review.
