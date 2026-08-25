# Regression Evidence

## Regression test added or strengthened

AF27 targeted tests pass 4/4. The complete executable suite passes 541 tests
with 14 existing skips when the sandbox-only socket case is excluded; the
current sandbox rejects `getsockopt(SO_TYPE)` with EPERM before that case can
exercise the server.

## Related tests executed

TODO

## Unaffected paths sampled

TODO
