# Verification

## Green command and result

- Original mode Red: PASS after the fix; a root-owned AF_UNIX socket with mode
  `0640` is rejected before socket construction.
- Wrong fixed-group and missing-group regressions: PASS before connection.
- Additional reviewer probes for `0600`, `0666`, `0670`, setgid `02660`, and
  setuid `04660`: all rejected before socket construction.
- Full source suite: 535 tests, 521 passed, 14 expected platform or sandbox
  skips, zero failures.
- Host Local Green: PASS for the full suite, repository validation, and exact
  `decision verify-product`; all commands returned zero within their deadline.
- `sddgov validate .`, `sddgov ci verify .`, and dependency `pip check`: PASS.
- Owner receipt import and reuse verification: Ed25519 signature, active key,
  repository audience, trust domain, expiry, exact request bytes, both signed
  assumptions, Option A summary, and current Owner-client identity PASS.
- Final wheel and source archive build plus Twine validation: PASS.
- Final offline bundle and fresh-wheel Codex/Hermes/demo/native-Linux smoke:
  PASS, with no source-checkout import and no real data.
- Declarative rollback drill: reverting the final R29 atomic product commit
  restored the exact trusted Base
  outside audit paths; setup-agent, Doctor, validate, and all 237 Base tests
  passed with one expected sandbox skip.
- Final Merge Gate preflight found that explanatory rollback prose must be
  comments under the declarative v3 parser. The prose was made inert without
  changing any rollback field; contract parsing, range, exact-tree rollback,
  and trusted-Base verification then passed.
- CodeRabbit exact-G review `5008019337` found two documentation contract
  mismatches. The canonical, installed, and packaged Hard Gates now state the
  required `shutdown(SHUT_WR)` request half-close byte-identically, and the WP
  now names bounded HTTP 429 and rate-limit-signalled 403 retries alongside
  connection and 5xx failures. The product runtime and signed Owner-client
  assumptions are unchanged.
- The review's duplicate trust-domain read was triaged as a deferred
  result-consistency refactor, not an authority expansion; changing it would
  require a new Owner-client decision. Its proposal to print masked raw release
  exceptions was rejected because local-path masking is not a complete
  terminal-control or public-error boundary.
- Independent R29 pre-sign review: PASS with zero unresolved findings; final
  hosted checks and the exact protected-file merge receipt remain separate
  post-Gate requirements.

## Before/after evidence

Red: exact R28 returned `True` for a root-owned `0640` socket. Green: the same
socket, every narrower or broader tested mode, a wrong fixed GID, and a missing
platform group all fail before socket construction, while the valid native
Linux AF_UNIX protocol remains Green.

## Remaining limitations

No live root Broker, real nonce, Production operation, package publication, or
private key is used. Native Linux and installed-wheel proof passed locally;
native macOS and the trusted-Base hosted Merge Gate remain required on the
exact pushed revision before Merge.
