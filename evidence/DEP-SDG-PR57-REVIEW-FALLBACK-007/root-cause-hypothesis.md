# Root Cause Hypothesis

## Hypothesis

The automated reviewer was treated as a mandatory availability dependency even when its own status said review was skipped, causing repeated rebuilds without adding review evidence.

## Supporting evidence

GitHub showed CodeRabbit success while the provider comment explicitly said review was skipped; CLI attempts also failed to return a usable exact-revision conclusion.

## Contradicting evidence

The signed independent reviewer, full Gate, rollback, Local Green, and hosted CI remained effective and independently verifiable.

## Falsification test

Encode one-attempt automated review semantics and require the signed independent review plus full Gate and hosted CI fallback when the provider skips or is unavailable.

## Conclusion

Confirmed by the machine contract tests, mirrored Policy Kernel validation, complete Local Green, and an actual rollback drill.
