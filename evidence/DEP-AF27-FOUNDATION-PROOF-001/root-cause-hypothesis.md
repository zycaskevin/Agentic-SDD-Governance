# Root Cause Hypothesis

## Hypothesis

The held FD is authoritative after pathname replacement, so its link count may
be zero without identity drift. Separately, a global os.name mock altered
pathlib before a test reached its intended helper. Both hypotheses are
confirmed by their paired Red/Green collectors.

## Supporting evidence

TODO

## Contradicting evidence

TODO

## Falsification test

TODO

## Conclusion

TODO
