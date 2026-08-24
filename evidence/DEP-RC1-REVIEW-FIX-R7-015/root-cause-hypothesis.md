# Root Cause Hypothesis

## Hypothesis

The R6 controls were individually fail-closed, but several surrounding proof and
developer-experience surfaces did not preserve the same end-to-end identity:
shell rendering could replace a pilot exit, Evidence publication retained host
paths, helper deadlines and wording were implicit, and current proof/rollback
commands were copied rather than re-executed against their exact representations.

## Supporting evidence

- A synthetic pilot writes a PASS JSON result and exits 7; R6 `demo/run.sh`
  rendered PASS and returned 0.
- Unix/macOS paths and literal or escaped Windows paths survived redaction; R6
  tracked shareable Evidence contained host workspace paths.
- `_run(timeout=...)` was unsupported, tests could wait indefinitely, and a
  manual workflow error incorrectly said “automatic”.
- The Work Package named an older DEP, R6 reported an inaccurate suite count,
  and its rollback expected the distribution version from a CLI that reports
  the governance VERSION. `--force` also changed the manifest timestamp.

## Contradicting evidence

The publish workflow is manual and intentionally non-cancelling; changing it to
automatic stale-run cancellation could interrupt a non-idempotent publication.
The broad CodeRabbit docstring percentage is not an acceptance criterion and
does not demonstrate a security, correctness, or interoperability defect.

## Falsification test

Exercise a PASS-result/nonzero-exit pilot, every supported local-path form across
small stream chunks, an explicitly forwarded timeout, the manual concurrency
diagnostic, current Work Package/rollback contracts, every tracked shareable
artifact, and a real isolated revert through Base tests and package install.

## Conclusion

Confirmed for the reproduced boundary and proof defects. The publication
concurrency and mass-docstring allegations are excluded as unsupported or
counterproductive to the established threat model.
