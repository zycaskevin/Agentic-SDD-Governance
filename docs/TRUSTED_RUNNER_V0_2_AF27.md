# AF27 Trusted Runner Production Containment Foundation

## Authority and invariant

AF27 implements the Linux primitives needed by the future production design,
but does not enable that design. `TrustedRunnerBootstrap` continues to reject
`mode=production` with `production_cgroup_containment_required`. This package
does not provision a service, create a cgroup on a host, read a credential, or
launch Hermes.

## Cgroup v2 descendant containment

The production path will accept only a delegated cgroup-v2 directory owned by
the Runner service. Before a child starts it must create a unique child scope,
write fixed `pids.max`, `memory.max` and `cpu.max` values, and move the child
PID into that scope. Timeout or cleanup must write `1` to `cgroup.kill`, then
observe `populated 0` in `cgroup.events` before removing the scope. Missing,
non-v2, symlinked, writable-by-other, malformed or non-empty scopes fail
closed. A process group is never accepted as an equivalent control.

## FD-bound runtime chain

The Runner must open the allowlisted runtime with `O_NOFOLLOW`, verify its
regular-file identity, ownership, permissions and SHA-256 while retaining that
same descriptor, and pass it to the minimal launcher. The launcher executes
only `/proc/self/fd/<verified-runtime-fd>`. Script/shebang runtimes are
rejected; therefore a mutable interpreter lookup cannot enter the chain. The
descriptor stays open until child completion and is closed on every failure.

## Offline acceptance

Synthetic tests use a disposable fake cgroup-v2 filesystem only to exercise
parsing and refusal paths; they cannot prove host delegation or kernel process
containment. A real cgroup scope is deliberately not created by AF27 tests.
The implementation must retain the AF26 hard deny until a separately approved
Operational Action provisions a dedicated UID, root-owned context, delegated
cgroup hierarchy, independent nonce broker and service manager integration.
