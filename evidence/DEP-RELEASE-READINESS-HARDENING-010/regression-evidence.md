# Regression Evidence

## Regression test added or strengthened

- `test_pr14_rollback_reconciliation_returns_doctor_and_tests_to_green` performs the historical rollback in a disposable clone, reconciles managed governance from the reverted source, and requires Doctor plus the declared test module to pass.
- `test_v3_rollback_requires_reconciliation_doctor_and_full_immutable_ref` rejects incomplete or weakened rollback contracts.
- `test_v2_postcondition_bootstrap_requires_exact_comment_contract` confines the Base-compatible transition bridge to the exact allowlisted fields.
- `test_manual_only_post_merge_verification_rejects_automatic_push` rejects a `push` event when post-merge verification is manual-only.
- `test_manual_only_push_cannot_hide_behind_workflow_exemption` permanently closes the independent-review bypass.
- `test_v1_contract_defaults_missing_post_merge_policy_to_automatic` provides the schema-1.0 migration path.
- `test_invalid_contract_mappings_fail_closed_without_exception` keeps malformed hosted/control mappings in a structured fail-closed report.
- `test_release_readiness_dep_uses_parseable_v2_bridge` parses the actual DEP-010 rollback bytes, preventing prose from silently invalidating the Gate.
- Repository-contract tests require one automatic PR route, one manual route, no automatic post-merge route, byte-identical packaged assets, and the clarified public/private review-sharing boundaries.

## Related tests executed

- 4 focused rollback/CI tests: PASS.
- 90 affected CI, Merge Gate, repository-contract, reviewer, and installer tests: PASS.
- Full repository suite: 205/205 PASS in 54.032 seconds.
- `sddgov validate`, `sddgov ci verify`, and `sddgov doctor`: PASS.
- Wheel and sdist build: PASS.
- Fresh dependency-resolved wheel install and `pip check`: PASS with `cryptography 50.0.0`.
- Fresh Codex and Hermes setup plus Doctor: PASS, 64 managed files each.
- Offline synthetic Muse pilot: PASS with no network or real data.

## Unaffected paths sampled

The full suite samples trusted Base separation, signed Review verification,
autonomy L0-L3 boundaries, Evidence/redaction transactions, installer
integrity, and the offline synthetic Muse pilot. Strict DEP, independent
Review, and the one bounded hosted run are recorded as separate completion
layers.
