# Verification

## Green command and result

The complete 257-test suite passed with two sandbox-only skips. Source
validation and installed Doctor passed. A new wheel and sdist passed Twine.
The release builder inventoried one project wheel, ten aarch64/CPython 3.12
runtime wheels, the exact governance lock, and a deterministic offline ZIP.
Fresh-wheel smoke verified every digest, installed dependencies with
`--no-index --require-hashes`, installed the project with `--no-deps`, then
passed Codex Doctor, Hermes Doctor, and the synthetic offline demo.

Focused results:

- Broker TERM/INT cleanup and restart: PASS.
- Bundle inventory, tamper, and symlink rejection: PASS.
- Protected environment contract and exact tag: PASS.
- Caller-selected benchmark threshold rejection: PASS.
- Logical-line newline/no-newline fail-closed cases: PASS.
- Machine-only ceremony and invalid-placeholder warning: PASS.
- Old Gate after implementation revert: correctly BLOCKED, exit 3.

## Before/after evidence

Before: the red artifact records all ten CodeRabbit findings and eight local
checks failing at the reviewed old Head. After: shareable logs bind the full
suite, validation, Doctor, Twine, bundle inventory, fresh-wheel smoke, and old
Gate invalidation to the new atomic implementation commit
`387b7d6052068ada9d07a9fbaadaf35758c42a5c`.

## Remaining limitations

- The local release-bundle proof is correctly labeled Linux aarch64/CPython
  3.12. The protected workflow refuses non-x86_64 runners and will create the
  separately labeled Linux x86_64/CPython 3.12 bundle.
- This sandbox cannot create a native Unix socket. Unit tests cover signal
  lifecycle with a controlled service double; native fixed-socket integration
  remains a release-host/WSL/macOS operational rehearsal.
- GitHub environments and their reviewer/admin/tag rules do not yet exist;
  TestPyPI, GitHub Release, and PyPI remain unpublished. The workflow preflight
  blocks before build until the external controls and read-only configuration
  token exist.
- Independent signed protected-file review and a fresh R2 CodeRabbit review
  remain required before a Gate-authorized merge.
