# Root Cause Hypothesis

## Hypothesis

Verifier separation worked as designed, but the rollback schema changed atomically from v1 to v2 without a compatibility generation that both the old trusted Base and new candidate verifier could validate.

## Supporting evidence

Base source requires `rollback_version`, `target`, `command`, and `verify` with version 1.0. Candidate source requires declarative v2 fields and rejects command strings. Hosted output is the exact Base rejection.

## Contradicting evidence

Receipt trust, exact change digest, checkout separation, dependency installation, and local candidate `MERGE_READY` all passed; the failure is isolated to schema migration.

## Falsification test

Add a parser that accepts v2 normally and only one exact legacy v1 command/verification pair, rejects duplicates, wrappers, chaining, extra fields, and no-ops; then select the existing strict v1 DEP for the migration gate.

## Conclusion

Confirmed. This is a trusted-verifier contract migration problem, not a transient runner failure; rerunning the unchanged revision is forbidden.
