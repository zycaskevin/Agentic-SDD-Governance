# Reproduction

## Expected

The L3 nonce-consuming client must reject the Broker before connection unless
the socket is root-owned, is an AF_UNIX socket, has exact mode `0660`, and uses
the fixed dedicated group (`sddgov` on Linux/WSL2 or `_sddgov` on macOS).

## Actual

On exact R28 Gate `a95b409962306da392443d83f8b40879b6f62e2e`, a
root-owned synthetic Broker socket with mode `0640` was accepted. The consuming
path also did not compare `st_gid` with the platform group's resolved GID.

## Deterministic steps

1. Use the exact R28 product code and construct root-owned parent metadata.
2. Present socket metadata with type `S_IFSOCK`, owner UID 0, and mode `0640`.
3. Return the exact framed `CONSUMED` response from the synthetic client.
4. Invoke `_consume_nonce_via_control_plane` as a non-root Agent identity.
5. Observe `True`; the new regression expects `False` and initially fails with
   `AssertionError: True is not false`.

## Environment and preconditions

Public PR #51, exact CodeRabbit review `5004583197` and inline finding
`3840740283`, Python 3.12, Linux. The locally redacted reproduction transcript
is registered as `shareable/artifacts/terminal--r29-code-review-red.txt`.
