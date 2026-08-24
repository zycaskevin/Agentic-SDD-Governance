# Root Cause Hypothesis

## Hypothesis

Readiness and daemon startup shared an exact socket owner/mode/group contract,
but `_consume_nonce_via_control_plane` independently implemented a weaker
owner/type/no-world-write check and never resolved the fixed group.

## Supporting evidence

The pre-fix consuming condition accepted `0640` because it checked only the
world-write bit. It never read `st_gid`; deterministic unit metadata therefore
reached the connection and accepted `CONSUMED`.

## Contradicting evidence

Parent-chain ownership, non-root Agent identity, socket framing, and readiness
checks were already fail closed. The defect is limited to the consuming
client's leaf metadata contract rather than the Broker protocol itself.

## Falsification test

Require supported POSIX platforms, the group database, exact `0660`, and exact
GID before socket construction; rerun mode, group, extra-byte, and real AF_UNIX
protocol checks.

## Conclusion

Confirmed. The runtime leaf check drifted from the documented readiness and
daemon contracts.
