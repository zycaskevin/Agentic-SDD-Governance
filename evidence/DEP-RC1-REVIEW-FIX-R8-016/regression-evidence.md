# Regression Evidence

## Regression test added or strengthened

Added or strengthened deterministic tests for slash-separated Windows paths, one- through four-dash private-key delimiter splits, closed-DEP pre-read rejection, blank/duplicate CI exemptions, exact permission-name errors, missing broker/pilot runtime files, user-guide command ordering, empty Proof DEP directories, Broker accept recovery, descriptor mutation/path replacement, manifest filename order, failure JSON reports, benchmark correctness state, transient-only API retry, workflow isolation/tag guards, and service hardening.

## Related tests executed

The exact focused suite passed after fix. Current Local Green executed 310 tests with 2 explicit skips, followed by repository validation. Package build, Twine, descriptor-bound offline bundle, and fresh-wheel Codex/Hermes smoke passed. The actual revert drill executed 229 Base tests with 2 explicit skips, Base build/Twine/version checks, and exact Base equality outside audit paths.

## Unaffected paths sampled

Autonomy signatures and nonce semantics, merge/reviewer verification, installer lifecycle, demo, synthetic pilot, schema validation, package metadata, canonical/package/installed parity, and predecessor R6/R7 portable-strict Evidence were exercised by the full suite. No external service or registry mutation was performed.
