# Regression Evidence

## Regression test added or strengthened

Added shell-level demo tests for rendered FAIL and missing-result status; one-source quick-demo checks plus nested-failure coverage; Broker `NOT_READY` aggregation; exact/unlisted release inventory; blank outer/inner CI exception names; Unicode case expansion before a private-key marker split across logical lines; and allowlisted Gate/Review descendants paired with rejection of a normal product descendant. Repository contract coverage also asserts inherited `PIP_*` removal and the intentional `BaseLoader` S506 suppression.

## Related tests executed

The exact implementation clone ran 271 tests with 2 environment skips and no failures. `sddgov validate`, `sddgov ci verify`, `sddgov doctor`, and `demo/run.sh` passed. Wheel and sdist built from the implementation commit passed twine; the offline aarch64 bundle passed exact-inventory verification; and the fresh wheel passed version, offline dependency install, Codex/Hermes setup/Doctor, and quick demo without importing the source checkout.

## Unaffected paths sampled

Autonomy L0-L3 classification and receipt tests, Evidence symlink/hardlink/FIFO/transaction tests, Reviewer signing, trusted-Base verification, CI permission controls, installer lifecycle, monorepo benchmark claim boundary, and release-environment checks remained Green. A separate revert clone returned to experimental.8, passed Doctor with 66 managed files, and ran 229 tests with the same 2 environment skips.
