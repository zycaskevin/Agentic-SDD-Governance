# Root Cause Hypothesis

## Hypothesis

The package is valid and the Owner runtime correctly rejects ambiguous topology. The failure is in the fresh-wheel harness: it creates a workspace through Darwin's fixed `/tmp` alias but later compares that logical spelling with CPython and module paths resolved through `/private/tmp`.

## Supporting evidence

- The hosted source suite, package build, installed Pilot, and demo all passed before the Owner runtime probe.
- The failure is the topology guard's exact generic rejection, not a RECORD, mode, signer, trust-store, or approval error.
- Darwin exposes `/tmp` as the fixed `/private/tmp` system alias, already handled by the shared bounded canonicalizer used throughout security-sensitive path walking.
- Ubuntu uses one spelling and the same complete job passed.

## Contradicting evidence

The production Owner venv is deliberately provisioned at the fixed root-controlled `/opt/sddgov-owner/venv` path and previously passed the exact non-signing runtime diagnostic. This does not contradict the hypothesis; the hosted rehearsal alone chooses a temporary alias path.

## Falsification test

Canonicalize the short smoke workspace once, before socket-length validation, venv creation, installation, and invocation. The hypothesis is falsified if the native macOS complete fresh-wheel smoke still fails, if source/import isolation changes, or if any Owner runtime check must be weakened.

## Conclusion

Confirmed. The smallest correction is harness-only and preserves the approved Owner client source identity and every fail-closed production custody boundary.
