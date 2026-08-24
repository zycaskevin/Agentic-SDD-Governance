# Regression Evidence

## Regression test added or strengthened

`test_fresh_smoke_workspace_falls_back_when_tmp_is_unavailable` now compares against `canonicalize_platform_path(Path(fallback))`. The adjacent Darwin-alias rehearsal remains unchanged.

## Related tests executed

The two focused release-bundle workspace tests passed locally. The candidate-plus-Evidence suite ran 524 tests with 14 expected skips and no failures. In the externally bound canonical repository, configured Local Green ran all 524 tests with 5 expected skips, validation, and the exact stored L2 product-decision verifier; every command returned zero.

## Unaffected paths sampled

The Owner-client digest inputs and signed L2 assumptions are unchanged. Production canonicalization, descriptor custody, and Linux fallback behavior remain covered by the existing suite. Build/Twine, the hash-locked offline bundle, a no-checkout-import fresh-wheel smoke, and an exact-tree Base rollback all passed.
