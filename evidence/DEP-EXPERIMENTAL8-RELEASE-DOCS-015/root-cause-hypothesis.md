# Root Cause Hypothesis

## Hypothesis

The experimental.8 engineering and security work intentionally kept publication separate, but the final release transaction did not include an explicit assertion that every current public installation example had advanced from experimental.6.

## Supporting evidence

The Red search deterministically finds stale download, bundle, heading, Changelog, and Roadmap strings even though `VERSION`, package metadata, tests, signed Merge Gate, and GitHub-hosted verification already identify experimental.8.

## Contradicting evidence

Historical Evidence and older-version Roadmap sections legitimately retain prior version numbers; the defect is limited to current installation and release-state instructions.

## Falsification test

Update only the five scoped public documents, then rerun the exact Red search. The hypothesis is falsified if any current experimental.6 install command or experimental.8 pre-release marker remains.

## Conclusion

Confirmed. Release documentation was not part of the final runtime-security assertion set. A bounded docs-only correction closes it without changing runtime behavior or authority.
