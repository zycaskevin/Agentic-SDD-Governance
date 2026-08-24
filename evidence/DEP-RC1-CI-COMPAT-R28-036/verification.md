# Verification

## Green command and result

`PYTHONPATH=src python -m unittest discover -s tests -v` completed 532 tests
with 14 expected platform/sandbox skips and no failures. Source validation and
CI Cost Guard verification both passed. The candidate wheel and sdist passed
build and Twine checks. The hash-locked offline bundle and fresh installed-wheel
smoke passed with no source-checkout import, Codex/Hermes Doctor validation,
the synthetic quick demo, and the real Linux AF_UNIX Broker suite. Exact
Owner receipt verification and the trust-bound Local Green both passed in the
fixed repository audience; all three configured commands used the 600-second
bound and returned zero. Reverting product commit
`7784f00b0125e9e30fd056ccf8f8407135d102f0` restored the exact trusted-Base
non-audit tree. Base setup/Doctor/validation, 237 tests, build/Twine, hash-locked
dependency installation, `pip check`, and a fresh installed-wheel consumer
setup/Doctor passed. Hosted and independent-review results remain final PR
postconditions and are not claimed by this local package.

## Before/after evidence

Before: a preserved legacy schema-1.0 contract failed `ci verify`, an exempt
workflow still produced a concurrency-group error, documentation misstated the
default source, and later large-fixture Git commands used the fixed timeout.

After: omission uses a bounded 600-second compatibility value in both
validation and execution; explicit invalid values still fail; exemption gates
the complete concurrency check; documentation distinguishes template and legacy
fallback; every fixture Git call receives the computed setup timeout.

## Remaining limitations

The duplicate trust-domain lookup remains a deliberate performance-only backlog
item. It does not change correctness or authorization, and modifying
`autonomy.py` solely for that optimization would invalidate the approved
Owner-client identity. Public package publication and production operations
remain outside this Work Package.
