# Root Cause Hypothesis

## Hypothesis

The R14 cleanup design confused the kernel socket inode returned by `fstat(fd)`
with the filesystem socket node returned by `lstat(path)`. It also bound at the
final pathname before it had a safely captured pathname identity, making the
first-stat failure impossible to clean both aggressively and replacement-safely.

## Supporting evidence

The real Linux Red transcript shows both objects are sockets and their identities
differ. PR #36 then raises `L3 Broker socket path changed immediately after
bind`. The global `_bound_socket_identity` mock in the old test class fabricated
equality. Linux documents `renameat2(..., RENAME_NOREPLACE)` and Darwin exposes
`renameatx_np(..., RENAME_EXCL)` for atomic no-clobber publication.

## Contradicting evidence

Client framing, signed approval verification, root-owned parent checks, ledger
serialization, and Darwin unified logging passed independent R14 review. The
defect is publication identity, not the cryptographic receipt or protocol.

## Falsification test

The hypothesis is false if the candidate compares fd and pathname identities,
can overwrite a final endpoint, deletes a synchronized replacement, fails to
answer health/restart with real syscalls, or passes only when socket/path helpers
are mocked.

## Conclusion

Confirmed. R15 binds an unpredictable socket name inside a descriptor-anchored
0700 staging directory, captures the staging pathname identity, publishes with
the platform's native atomic no-clobber primitive, and thereafter removes the
final node only when its captured pathname identity still matches.
