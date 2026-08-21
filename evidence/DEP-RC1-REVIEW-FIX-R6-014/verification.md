# Verification

## Green command and result

PASS: focused 113-test regression matrix, final 290-test Local Green,
repository validation, source build, Twine inspection, locked offline release
bundle assembly, and fresh-wheel Codex/Hermes smoke all passed. Two existing
tests were explicitly skipped because the execution sandbox forbids Unix socket
creation and lacks one historical rollback object; neither was reported PASS.

## Before/after evidence

Before, R5 accepted unbound release bytes, mutable installation inputs, inherited
Broker deadlines, incomplete validation results, and post-redaction raw additions.
After, each operation consumes a private verified generation or exact schema/
metadata binding, and later Evidence collection fails before changing manifest or
raw inventory. Attached reports carry exact review, Red, Local Green, bundle, and
fresh-wheel results.

## Remaining limitations

Protected files changed, so Merge remains blocked without an independent signed
review receipt on the final exact Head. TestPyPI/PyPI byte round trip, OIDC
environment protection, attestations, GitHub Release, real key ceremony, root
Broker installation/WSL2 rehearsal, and any sensitive-data pilot remain external
or environment-specific gates; none is claimed complete by local proof.
