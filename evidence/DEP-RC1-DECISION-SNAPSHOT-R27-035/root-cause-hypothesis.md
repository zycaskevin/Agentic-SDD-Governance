# Root Cause Hypothesis

## Hypothesis

The verifier lacked an explicit call-wide snapshot ownership boundary, and the
snapshot cache treated its first read limit as permanent even when a later
consumer required a stricter bound.  Separately, the Local Green contract did
not model a per-command deadline.

## Supporting evidence

R26 called `_read_repository_regular_file`, `_verify_product_envelope`, and the
marker artifact reader independently.  `FileSetSnapshot.read` returned cached
bytes immediately.  `subprocess.run` in the Local Green loop had no timeout.

## Contradicting evidence

R26 signature verification, ordinary unit tests, rollback, and hosted Linux and
macOS all passed.  Those checks did not substitute file generations between
verification phases or repeat one retained read under a smaller bound, so they
do not contradict the hypothesis.

## Falsification test

Make `verify_product_decision` create one `FileSetSnapshot`, pass it into the
single envelope verification, reuse its exact request/assumption bytes for all
semantic checks, and return only after context-exit reconciliation.  Reapply a
smaller bound on cache hits.  Add hostile generation-substitution and
large-then-small regressions.  Add a validated Local Green command timeout and
a timeout/lock-release regression.

## Conclusion

Confirmed.  The targeted regressions fail against the R26 behavior and pass
after the bounded R27 changes.  The current Owner-client identity changed, so
the R26 Owner decision is correctly reopened rather than silently reused.
