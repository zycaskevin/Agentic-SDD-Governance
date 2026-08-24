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
- Full source, Local Green, package, rollback, hosted, automated-review, and
  independent-review results remain pending until the final R30 topology.

## Before/after evidence

Red: exact R29 streamed both synthetic value fragments to the shareable file
and reported no replacement. Green: the same bounded bytes produce the exact
whole-text replacement and count; unsafe incomplete variants publish nothing.

## Remaining limitations

No real credential, private key, user data, package publication, root service,
or nonce consumption is involved. Native macOS and the trusted-Base hosted
Merge Gate must pass on the exact pushed R30 revision before Merge.
