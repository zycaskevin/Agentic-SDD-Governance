# Reproduction

## Expected

The complete installed-wheel rehearsal should use one absolute spelling for its independently installed venv and pass on both Linux and macOS without relaxing any Owner runtime custody check.

## Actual

PR #51's Ubuntu job passed. The macOS-15 job completed source Green, package construction, installed Pilot, and the demo, then failed in `fresh_wheel_smoke.py` when `_require_owner_runtime` rejected the installed venv as not being invoked by one absolute reviewed path.

## Deterministic steps

1. Run the complete fresh-wheel smoke on a native macOS host with its short workspace created under the fixed `/tmp` system alias.
2. Create the venv and launcher from that logical spelling.
3. Observe CPython/package paths resolve through the fixed `/private/tmp` target while the launcher environment still carries the logical alias.
4. Observe the exact Owner runtime topology comparison fail closed before any TTY, signer, or receipt operation.

## Environment and preconditions

Hosted Red is GitHub Actions run 32652106387, macOS-15 job 97225221188, at Gate Head `854ce5193d6e106e02622670dc95b9f25cf4e334`. The Owner decision, request, eight-file client identity, public receipt, signer custody, and root-controlled trust stores were unchanged and were not accessed for this diagnosis.
