# Reproduction

## Expected

Review findings that cross security or release boundaries are reproduced before
implementation. Demo failures remain nonzero; all shareable Evidence masks local
user paths, including escaped Windows tracebacks; test/package commands are
bounded; current proof and rollback commands are exact and executable.

## Actual

The first focused run executed 86 tests and exited 1 with six failures and two
errors. It reproduced the demo exit masking, missing path redaction/inventory,
unbounded fresh-wheel helper, inaccurate hosted-workflow wording, stale Work
Package binding, and exposed R6 paths. A first full 297-test run then failed on
the escaped form `C:\\Users\\...`, proving the initial path detector incomplete.

## Deterministic steps

On reviewed PR #28 Head `5f7488008cded952f4e0470e01d69979a528829f`,
run the focused modules recorded in `terminal--r7-red-tests.txt`. After the first
fix, run the full Local Green command recorded in
`terminal--r7-escaped-path-red.txt`; the repository-contract path inventory must
fail until both literal and escaped Windows separators are recognized.

Review node IDs and exact `discussion_r...` URLs are preserved in
`git--r7-review-bindings.txt`. The workflow-dispatch concurrency allegation is
not reproduced: only automatic workflows require stale-run cancellation, while
non-idempotent publication deliberately uses `cancel-in-progress: false`.

## Environment and preconditions

Linux aarch64, Python 3.12, trusted Base
`1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. No Production, registry, tag,
release, credential, real Owner key, root Broker service, or real nonce was used.
