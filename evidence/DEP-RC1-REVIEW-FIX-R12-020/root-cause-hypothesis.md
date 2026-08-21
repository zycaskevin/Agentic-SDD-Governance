# Root Cause Hypothesis

## Hypothesis

The review failures came from incomplete authority, framing, capacity, and deployment contracts rather than one algorithmic defect. The Broker accepted a first complete record without proving connection closure, allocated its active nonce set before checking a prospective append, and allowed caller environment to select trust authority. The release/deployment layer also left host/interpreter/log-retention preconditions implicit, while several compatibility and historical-evidence statements had drifted from current behavior.

## Supporting evidence

The focused Red transcript fails at each affected API, service asset, workflow, and repository contract. The delayed-second-record test proves the handler could reach readiness or consume before complete framing was known. The near-limit test makes `_scan_locked` explode, proving capacity was checked too late. Trust substitution tests return ready under caller-selected state before the fix. PR review IDs, exact paths, and dispositions are preserved in `git--r12-review-bindings.txt`.

## Contradicting evidence

The current and trusted-Base suites otherwise remain Green, so the evidence does not support weakening the Hard Gate, adding a production mock Broker, making the trusted path configurable by the Agent, switching exact-tree rollback to affected paths, or claiming benchmark superiority. The proposed systemd `SystemCallFilter` is not demonstrated safe for the exact deployed interpreter and cryptography runtime, so it remains deferred to target-host rehearsal.

## Falsification test

Add focused assertions for EOF-bound one-record framing, rejection before validation/consume, capacity rejection before `_scan_locked`, fixed trust authority and override rejection, guarded offline downloads, launchd identity/umask/executable/rotation, pinned protected-job Python, runtime dependency separation, public resource access, exact CI exemption behavior, platform-aware tests, and 80 percent ledger telemetry. The hypothesis is falsified if these assertions pass on the reviewed Head without the bounded changes, or if the corrected candidate cannot pass package proof and exact-tree Base rollback.

## Conclusion

Confirmed. The reviewed Head reproduced the bounded failures and the R12 candidate passes the focused assertions, 357-test current suite, source validation, isolated package/Twine/offline/fresh-wheel proof, and an actual rollback drill. Reverting the single-parent atomic product commit restores the non-audit tree exactly to Base while retaining Evidence, Merge Gate, and review audit descendants.
