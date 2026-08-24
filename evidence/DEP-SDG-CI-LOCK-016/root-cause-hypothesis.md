# Root Cause Hypothesis

## Hypothesis

`run_local_gate` has no current-user cross-process critical section. Sequential
iteration over `local_green.commands` prevents overlap only inside one Python
process and provides no coordination across Builder/Reviewer checkouts.

## Supporting evidence

- `run_local_gate` calls `verify_guard`, reads the contract, and immediately
  executes each configured command.
- The module imports no locking primitive and creates no coordination record.
- The RED orchestration test proves there is no boundary to enter before
  verification or command execution.
- The triggering Vault verifier deterministically denies when a competing
  sibling mutation changes a retained shared ancestor.

## Contradicting evidence

- The triggering Vault failure intentionally erased its exact verifier
  subcondition after the temporary node was cleaned.
- Direct repository runner invocations that bypass `sddgov` would not be
  covered by an orchestration-layer lock.

## Falsification test

Add a current-user advisory lock to `run_local_gate`, acquire it before
`verify_guard`, and hold it through every configured command. Prove a competing
descriptor cannot enter while held and prove both verification and commands
observe the locked state. If those tests pass but overlapping `sddgov` gates
still enter concurrently, reject the hypothesis.

## Conclusion

The missing cross-process orchestration boundary is confirmed at the source
level and by RED. The exact historical Vault denial remains supporting context,
not the sole causal proof.
