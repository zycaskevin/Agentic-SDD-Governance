# Root Cause Hypothesis

## Hypothesis

R8 validated final pathnames and file descriptors but did not retain every ancestor-directory generation, so a validated pathname could still be redirected between operations. Other findings came from enforcing limits or parity at a later layer than the actual trust boundary: Evidence size after reading, CI exceptions without inventory binding, benchmark failure reports outside the success schema, and prose/service assertions that were semantically present but not exact or mirrored.

## Supporting evidence

The focused Red run reproduced each boundary failure. Synthetic directory replacement found no retained directory abstraction; an oversized collector input reached publication logic; an absent workflow exception passed; a 429 response escaped without bounded retry/close; invalid slugs reached the API; nested wheel paths were accepted; fresh-smoke could not create a new report parent; and benchmark, README, and rollback contracts lacked required fields or ordering.

## Contradicting evidence

R8 package, full-suite, and rollback proofs showed that the principal governance design remained sound. The findings did not invalidate the Policy Kernel, Ed25519 receipt validation, trusted-Base verifier isolation, exact-tree rollback algorithm, or offline release inventory. They were bounded enforcement and DevEx gaps around those controls.

## Falsification test

Open each release directory component with `O_DIRECTORY|O_NOFOLLOW`, retain its descriptor, perform enumeration and I/O descriptor-relatively, and reject generation replacement. Enforce the Evidence byte ceiling both before and during reading. Add exact negative tests for every adjacent contract, then require focused tests, the 323-test Local Gate, isolated build/Twine, offline bundle/fresh-wheel proof, and an actual Base rollback drill to pass.

## Conclusion

Confirmed. Retained directory/file descriptors and owned-generation checks close the release ancestor TOCTOU gap. Early bounded reads, shared safe cleanup, strict CI/repository validation, common benchmark reports, exact mirror assertions, and ordered documentation close the remaining findings without weakening fail-closed behavior.
