# Root Cause Hypothesis

## Hypothesis

Four contracts drifted: release floors were not maintained against reviewed
advisories; socket identity was captured too late; macOS combined incompatible
pathname writers/rotators; and installed-asset validation lacked one inventory.

## Supporting evidence

Red records the unsafe pin and launchd/newsyslog conflict. Hostile Broker tests
reproduce stranded-original and replacement-preservation boundaries. Contract
tests fail if the removed asset survives in any source or package surface.

## Contradicting evidence

The prior receipt digest was valid when issued, so this is not a signature or
digest bypass. `wheel==0.48.0` was already above its reviewed safe floor.

## Falsification test

The hypothesis is false if an affected pin remains, cleanup keeps the original
or deletes a replacement, pathname/newsyslog configuration survives, sensitive
request data reaches logs, or a missing required service asset passes Doctor.

## Conclusion

Confirmed. R14 raises the floors, binds cleanup to descriptor identity, uses
Darwin unified logging, reconciles all asset mirrors, and adds direct tests.
