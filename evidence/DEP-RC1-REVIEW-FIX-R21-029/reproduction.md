# Reproduction

## Expected

Every public file and socket publication is bound to the exact generation produced by its retained descriptor, and any failed cleanup preserves a later writer. Streaming and whole-buffer redaction cover the same sensitive representations or fail closed. Release downloads and operational control files remain machine-verifiable.

## Actual

R20 independent review reproduced valid substitution, close-boundary, claim-boundary, supplied-dirfd, cross-line, escaped-UNC, and release/control-plane provenance failures. Several happy-path tests passed while the unmodeled boundary still failed.

## Deterministic steps

1. Swap regular, symlink, hardlink, and FIFO generations after Evidence control, attachment, and redaction staging but before publication.
2. Force descriptor close to close successfully and then raise; replace the visible generation before cleanup and inspect both the final name and staging residue.
3. Split every supported sensitive field across newlines and split native plus JSON-escaped WSL UNC paths across streaming chunks.
4. Replace an Evidence output parent after its retained dirfd is acquired, and assert no entry is created through the replacement pathname.
5. Swap Broker socket and regular-file names at cleanup claim boundaries, including a leaf near `NAME_MAX`.
6. Tamper or add a release asset between downloads and verify the full inventory is rejected.

## Environment and preconditions

R20 Gate Head `589129dd3e67f0de25aae540146f58acb7c97757` on Linux aarch64 with Python 3.12; hosted Darwin checks and exact trusted-Base verification remain required.
