# Regression Evidence

## Regression test added or strengthened

- `test_stored_product_decision_reverifies_signature_row_audience_and_request`
  now proves one envelope verification receives the call-wide snapshot and
  rejects an assumption generation substituted after digest verification.
- `test_file_set_snapshot_reapplies_a_smaller_bound_to_cached_bytes` proves a
  300 KiB retained file cannot pass a later 256 KiB bound.
- `test_card_rejects_a_self_assumption_over_the_per_artifact_bound` proves the
  1 MiB request read cannot bypass the 256 KiB self-assumption bound.
- CI Guard tests require a 1..3600 second timeout and prove timeout failure
  releases the Local Green lock.

## Related tests executed

The focused filesystem, autonomy, Owner approval, and CI Guard set executed 159
tests: 158 passed and one expected sandbox AF_UNIX skip.  The final complete
sandboxed suite executed 528 tests: 514 passed and 14 platform/sandbox skips.
The host Local Green executed the same 528 tests with 523 passes and five
platform-only skips, then validated the repository and cryptographically
reverified the exact Owner decision from its fixed repository audience.
Package, fresh-wheel, rollback, and exact trusted-Base results are recorded in
`verification.md`.

## Unaffected paths sampled

Agent-side root refusal and Owner-only fixed trust routing, L3/Broker
classification, release workflow permission exceptions, managed mirror parity,
Darwin canonical aliases, current-main Draft guards, and release-note privacy
remain covered by the existing suite.
