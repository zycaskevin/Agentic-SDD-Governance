# Regression Evidence

## Regression test added or strengthened

- Reject setuptools below 83.0.0 and wheel below 0.46.2.
- Remove the created socket on identity failure and preserve replacements.
- Use Darwin unified logging without sensitive request/nonce/payload/digest
  data; keep success and duplicate consumption silent.
- Reject any surviving newsyslog/pathname asset and fail on missing required
  remaining service assets.
- Record configured/resolved Python, total/payload bundle counts, and mode 0700.

## Related tests executed

The isolated environment ran 366 tests successfully with two explicit
sandbox-only socket skips. CI verify and Local Gate passed. `setuptools==83.0.0`
and `wheel==0.48.0` built RC1 wheel/sdist; Twine passed. Offline fresh-wheel
smoke passed Codex/Hermes with 71 managed files each, 13 total/12 payload files,
no checkout import, and a Green synthetic demo.

## Unaffected paths sampled

Autonomy receipts, DEP lifecycle, reviewer signatures, merge digest, CI
permissions, release environment, installer parity, and pilot all passed. The
rollback drill passed 229 Base tests, Base Doctor/Validate/build/Twine, and a
clean installed-consumer smoke.
