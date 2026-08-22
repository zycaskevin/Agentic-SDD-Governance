# Verification

## Green command and result

The focused CI Guard suite passed all `27` tests. Targeted changed-file Ruff
safety rules (`E4,E7,E9,F`), source validation, managed-copy parity, and diff
checks passed. The exact committed
head `196685c2680da9a84d4b5efd35dd66f20909f1b4` then passed the complete
repository Local Green Gate: `237` total tests, comprising `236` passed and one
platform-dependent skip; governance source validation also passed. The
post-run worktree was clean.

## Before/after evidence

RED is preserved in `shareable/artifacts/terminal--artifact-1.txt`; focused
Green is preserved in `shareable/artifacts/terminal--artifact-2.txt`; exact-head
Proof is preserved in
`shareable/artifacts/terminal--exact-head-local-green.txt`.

Before: independent `run_local_gate` callers had no shared critical section.
After: the same real child process confirms a nonblocking acquisition was
denied while the parent holds the lock, reports `blocked`, acquires the lock
after release, and exits successfully;
verification and commands run inside the critical section; symlink/permissive
records fail closed; inner failure releases the descriptor lock.

## Remaining limitations

The orchestration lock covers only callers using `sddgov` Local Green. It is a
POSIX-user contract; existing package code already depends on `fcntl`. Direct
commands outside `sddgov` and hosted jobs in separate environments are outside
this bounded contract.

The first full orchestration attempt did not produce a Green result: it found
the nested unit-test deadlock described in `regression-evidence.md`. A second
observer command waited on that same experimental lock and was stopped with
exit `130`; it did not execute repository tests. Neither attempt is claimed as
Proof. The subsequent fix changes test isolation only and keeps production
serialization fail closed.

The exact `ab0396b...` gate then reached the merge-verifier unit that performs
one intentional nested Local Green and waited on the production lock. It was
stopped with exit `130`, not claimed as Green, and corrected with a synthetic
test-only lock root. The formerly blocked merge node and all focused lock tests
now pass. The final committed head subsequently completed Local Green with exit
`0`; no failed attempt is retroactively claimed as Green.
