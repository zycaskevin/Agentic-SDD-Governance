# SDG-CI-LOCK-001: Concurrent Local Green gates are not serialized

Status: verified locally

## Problem

`sddgov ci local-gate` runs each configured command sequentially inside one
invocation, but independent invocations for the same current user can overlap.
Repository-controlled gates that intentionally share owner-private runtime
roots can then mutate one another's filesystem ancestors and produce transient
fail-closed results despite unchanged repository bytes.

This was observed while validating Vault Agent Memory VAM-006A: two exact-head
gates failed at different points inside the same identity-sensitive node, and a
deterministic verifier probe proved that sibling creation below the shared node
root invalidates retained absolute-path identity.

## Expected behavior

- One current user has at most one active `sddgov` Local Green critical section.
- The lock is acquired before contract verification or repository commands.
- A second invocation waits; it does not retry, cancel, or weaken either gate.
- A crash releases the advisory lock through descriptor closure.
- The persistent coordination record contains no repository data or secrets.

## Non-scope

- Repository test selection, acceptance criteria, retries, HOME/TMPDIR values,
  hosted CI concurrency, merge policy, or Reviewer trust.
- Vault Subject runner/verifier changes or VAM-006A product behavior.
- Push, release, installation into a shared runtime, or production action.

## Closure evidence

The atomic orchestration implementation is the direct parent of the DEP Proof
commit, where its exact revision is machine-bound. Deterministic cross-process,
fail-closed, exception-release, and nested-test-isolation regressions pass. The
same exact implementation revision passed the complete repository Local Green
Gate with `234` tests passed, one platform-dependent skip, and governance
source validation Green. No shared installation, release, merge, or consumer
runtime mutation was performed.
