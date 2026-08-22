# Root Cause Hypothesis

## Hypothesis

The release-note proof copied an exact downstream reproducer outcome that
belongs in governed Evidence, not in the public summary.

## Supporting evidence

The affected sentence is the only current release-note occurrence of a
downstream-specific name, pull-request form, and unpublished-state marker.

## Contradicting evidence

The exact context is useful for local traceability and already exists in
Issue #44 Evidence, so deleting it from all records would reduce auditability.

## Falsification test

Replace only the public sentence with generic verified behavior, then rerun the
bounded privacy assertion and confirm the runtime diff is empty.

## Conclusion

Confirmed. The public sentence copied exact downstream traceability context;
the same detail is already retained in governed Issue #44 Evidence, so only
the public wording must change.
