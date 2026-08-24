# Regression Evidence

## Regression test added or strengthened

`test_l3_broker_rejects_noncanonical_socket_mode_before_connection` preserves
the original Red. `test_l3_broker_rejects_wrong_socket_group_before_connection`
proves GID mismatch fails before socket construction. Existing fragmented and
extra-response tests preserve protocol framing.

## Related tests executed

The final source suite executed 535 tests: 521 passed and 14 platform or
sandbox cases were skipped. The host Local Green execution also ran 535 tests
with five platform skips, then validated the repository and cryptographically
reverified the exact Owner decision, request, assumptions, audience, expiry,
and current Owner-client identity. All three Local Green commands returned
zero within their 600-second per-command bounds.

The affected autonomy, Broker, and Owner approval suite passed before the
Owner decision. After receipt import, the complete suite exposed one stale
repository-contract expectation that still named the R28 assumption hashes.
The test-only constants were corrected to the exact R29 assumption bytes, and
the complete suite then passed without changing either signed assumption.

The final wheel and source archive built under the hash-locked governance and
release environment and passed Twine validation. A newly generated offline
bundle contained ten dependency wheels plus four public assets. Fresh-wheel
smoke imported no source checkout, verified the Owner approval client, set up
and diagnosed both Codex and Hermes with 73 managed files, ran the synthetic
demo without real data, and passed the native Linux AF_UNIX Broker suite.

The final Merge Gate preflight also exercised the declarative rollback parser.
It rejected non-comment explanatory prose, so those inert lines were converted
to comments while the exact v3 fields and product rollback reference remained
unchanged. Parser, candidate-range, and clean-revert checks then passed.

CodeRabbit exact-G review `5008019337` subsequently reported inline comments
`3843644826` and `3843644844`. The first showed that the normative Broker text
omitted the client request half-close required by the existing implementation;
all three governed copies now specify `shutdown(SHUT_WR)`. The second showed
that the WP omitted bounded rate-limit retries already implemented for HTTP 429
and rate-limit-signalled 403 responses; the acceptance text now names the exact
classes, three-attempt limit, and 60-second delay cap. Mirror parity and the
complete suite cover the corrected contracts.

## Unaffected paths sampled

Repository validation, CI Guard verification, decision verification, Evidence
portability, package RECORD and source parity, demo behavior, Codex/Hermes
installation, redaction transactions, release helpers, and the complete Base
rollback suite were sampled. No Production operation, real nonce consumption,
package publication, private key access, or root Broker installation occurred.
