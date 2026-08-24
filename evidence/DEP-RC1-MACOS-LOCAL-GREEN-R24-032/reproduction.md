# Reproduction

## Expected

The complete source suite should pass on both Linux and macOS while enforcing one canonical repository root in trust-domain checks. Running the configured Local Green should serialize concurrent top-level gates without deadlocking on unit tests that exercise the gate itself.

## Actual

GitHub Actions macOS-15 ran 523 tests and stopped before packaging with 21 failures and 34 errors. Most failures reported that the synthetic approver was not authorized for the tempfile repository root; the synthetic distribution test failed before its intended duplicate-target assertion. Separately, a local top-level gate held the per-user lock while its complete-suite child reached a unit test that attempted to acquire the same lock and waited indefinitely.

## Deterministic steps

1. Run the source suite on a native macOS runner whose temporary directory is exposed through `/var` or `/tmp`.
2. Observe product code canonicalize the system alias to `/private/var` or `/private/tmp` while the synthetic trust-domain fixture retains the logical alias.
3. Observe the exact-root comparison fail closed before the intended unit-test assertion.
4. Start the configured Local Green on Linux.
5. Let its complete-suite command reach `test_bare_python_command_uses_the_locked_cli_interpreter`; observe the nested `run_local_gate` wait on the parent process's per-user lock.

## Environment and preconditions

Hosted Red is GitHub Actions run 32650764504, macOS-15 job 97221883306, at Gate Head `f52d6cb95ee39c72bf43969b8cde97cef49edf6b`. Local Red used the same candidate under Python 3.12. The signed Owner receipt and its governed source/request assumptions were unchanged; no Owner signer or private material was used during this diagnosis.
