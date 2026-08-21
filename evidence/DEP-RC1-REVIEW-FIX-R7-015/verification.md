# Verification

## Green command and result

PASS: full Local Green executed 297 tests with 2 explicit sandbox skips, then
repository validation and local CI-cost checks passed. Source build and Twine
inspection passed; the aarch64 offline bundle bound ten locked dependencies; a
fresh wheel imported no source checkout and passed Codex/Hermes Doctor,
validation, bundle verification, and the offline demo. The corrected isolated
rollback drill executed 229 Base tests with 2 explicit sandbox skips, rebuilt and
installed the Base wheel, verified both version identities, and restored exact
Base outside audit paths.

## Before/after evidence

Before, a pilot exit 7 became shell exit 0, host paths survived shareable
redaction, timeout/wording/proof bindings were incomplete, and copied rollback
commands did not match Base version semantics. After, each has a focused
regression and the final Proof includes both the intermediate escaped-path failure
and an end-to-end rollback transcript rather than a documentation-only claim.

## Remaining limitations

Protected files changed, so Merge remains blocked until an independent reviewer
approves and signs the final exact Head. TestPyPI/PyPI byte round-trip, protected
environments, public attestations/GitHub Release, real Owner key ceremonies, root
Broker installation/WSL2 rehearsal, and sensitive-data pilots remain explicit
external actions. None is claimed complete by this local Evidence package.
