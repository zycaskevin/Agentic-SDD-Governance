# Root Cause Hypothesis

## Hypothesis

R5 established the release and operations surfaces, but several security checks
stopped at inventory or schema shape rather than binding the bytes, metadata,
deadlines, and post-publication identities that the later operation actually
uses. Documentation and pilot code also assumed optional host tools or complete
nested results instead of validating those assumptions at the boundary.

## Supporting evidence

- Red accepts a dependency digest absent from the lock and archives whose
  embedded version differs from `0.2.0rc1`.
- Fresh-wheel smoke verifies one path and then installs original mutable paths.
- Broker responses inherit the shrinking read timeout; unavailable Ed25519
  backends escape readiness normalization.
- Redaction can publish before registering its inode for transaction cleanup,
  and a dash-only unittest separator matches an incomplete private-key prefix.
- A consumer `pyproject.toml` is mistaken for the SDG source tree; empty CI job
  exception maps and incomplete pilot results pass boundary checks.
- `collect` accepts new raw bytes after `redaction-report.json`, producing a
  stale inventory that strict verification later rejects.

## Contradicting evidence

The R5 exact-Head gate audit remains internally consistent. The repository also
intentionally permits builders to modify protected service assets while requiring
an independent signed review before Merge. Those findings do not justify changing
the trusted-base or protected-file policy.

## Falsification test

Alter one boundary at a time: lock hash, embedded archive version, original bundle
generation after snapshot, response timeout, crypto backend, post-publish inode,
source marker, empty exception map, missing nested pilot key, dash-only line, and
post-redaction collection. Each must fail on R5 and pass only after its boundary
is explicitly bound or closed.

## Falsification results

`shareable/artifacts/terminal--r6-red-tests.txt` records the pre-fix boundary
failures, while `shareable/artifacts/terminal--r6-local-green.txt` records the
same focused cases and the 289-test R6 suite passing after the bindings were
implemented. The exact PR review identities and reviewed Head are preserved in
`shareable/artifacts/git--r6-review-bindings.txt`. No falsification result was
inferred from the later conclusion text.

## Conclusion

Confirmed. The reproduced defects share a missing end-to-end binding at an
otherwise fail-closed boundary; the merge-gate self-review allegation is excluded
because it was not reproduced.
