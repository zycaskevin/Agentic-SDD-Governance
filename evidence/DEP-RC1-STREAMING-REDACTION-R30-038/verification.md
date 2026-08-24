# Verification

## Green command and result

- Original multiline quoted password Red: PASS after the fix; streaming output
  and totals equal whole-text redaction and no synthetic value fragment remains.
- Both quote styles and two password plus two named-secret spellings: PASS.
- Unterminated, over-limit, and invalid physical-line escape cases: PASS with
  no current or prior owned publication left behind.
- Affected redaction suite: 45 tests PASS.
- Complete source suite: 537 tests, 523 PASS and 14 expected platform or
  sandbox skips.
- `sddgov validate .` and `sddgov ci verify .`: PASS.
- Owner-client identity: unchanged and equal to the signed Decision request.
- Candidate wheel and sdist build: PASS; Twine validation: PASS.
- Candidate wheel SHA-256:
  `e8148ec64f8809da567bf9f8ca3e14774244d207316195d7020eaad62861f766`.
- Candidate sdist SHA-256:
  `a3d15308e41adeecfc3b51a9c41b934c8bfdd488b226885870962c9ca57642de`.
- Offline release bundle: PASS with 10 dependency wheels and four public
  assets. Fresh installed-wheel smoke: PASS outside the source checkout;
  `source_checkout_imported=false`, bundle 13 files/12 payload files, Codex
  and Hermes Doctor/validation each reported 73 managed files, the synthetic
  quick demo passed, and native Linux Broker checks passed.
- Actual declarative rollback rehearsal: PASS. Reverting
  `01e882a3a2a8fa98fc062110fdc0f273b03065c8` at the Evidence Head restored
  the exact trusted-Base non-audit product tree. Base setup-agent, Doctor,
  validation, package build, and Twine validation passed; the Base suite ran
  237 tests with one expected sandbox skip and no failure.
- Canonical Owner-bound Local Green at Evidence Head
  `b5c5d1af52ab2765b74b84632093d540879db73e`: PASS. It executed all 537
  tests with five host-platform skips, repository validation, and the exact
  stored L2 product-decision verification. The receipt remained bound to the
  active Owner key, repository audience, request, assumptions, and current
  Owner-client identity; expiry is `2026-09-23T12:17:28Z`.
- Hosted, automated-review, and independent-review results remain pending
  until the final R30 Evidence Head and Gate are frozen.

## Before/after evidence

Red: exact R29 streamed both synthetic value fragments to the shareable file
and reported no replacement. Green: the same bounded bytes produce the exact
whole-text replacement and count; unsafe incomplete variants publish nothing.

## Remaining limitations

No real credential, private key, user data, package publication, root service,
or nonce consumption is involved. Native macOS and the trusted-Base hosted
Merge Gate must pass on the exact pushed R30 revision before Merge.
