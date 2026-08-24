# Root Cause Hypothesis

## Hypothesis

Darwin's `sockaddr_un.sun_path` limit applied to the complete nested staging
pathname, but the native test and fresh-wheel harness relied on the host's long
default temporary directory. The test therefore failed before it could exercise
the no-clobber primitive. Source-checkout imports also left package provenance
unproven on native CI.

## Supporting evidence

The hosted macOS stack traces all stop at `server.bind(str(staging_path))` with
`AF_UNIX path too long`; Linux passes. The fixed Darwin production staging path
is 83 encoded bytes, below the 103-byte NUL-terminated boundary used by the
test. Local `/tmp/sgb-*` source and installed-wheel runs reach all eight tests.

## Contradicting evidence

The R15 descriptor-anchored publication algorithm passed all Linux semantic
tests, including native atomic no-clobber. This is not a failure of
`renameatx_np`, receipt validation, or socket identity preservation.

## Falsification test

The hypothesis is false if a short-root native test still fails before rename,
the fixed production staging path exceeds the asserted Darwin boundary, the
workflow imports checkout `src`, or installed-wheel Linux/Darwin jobs diverge.

## Conclusion

Confirmed. R16 bounds the native harness path, checks the fixed Darwin path,
uses the same bound in fresh-wheel smoke, and builds/installs the candidate wheel
before executing real AF_UNIX tests outside the checkout import path.
