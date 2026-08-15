# Reproduction

## Expected

The verifier is loaded from an immutable trusted base, every portable Evidence artifact is independently reopened and recalculated, local raw artifacts are recalculated when required, filesystem links and escapes fail closed, and L2/L3 continuation requires exact trusted-owner authorization.

## Actual

Synthetic adversarial cases were accepted by the released verifier: modified or absent artifacts still verified, bounded directories could be escaped or linked, duplicate labels overwrote evidence, and caller-controlled classification or decision records could produce `CONTINUE`.

## Deterministic steps

1. Install the published experimental.6 wheel in an isolated virtual environment.
2. Copy a synthetic Proof-phase DEP and modify or move its shareable artifact without updating the manifest.
3. Run strict verification and observe success.
4. Exercise a traversal DEP ID, per-file redaction links, and duplicate collector labels inside a disposable temporary directory.
5. Evaluate synthetic L1 product/high-risk requests and a caller-created L2 decision.
6. Inspect the PR workflow verifier checkout and import path.

Exact exploit-oriented command output remains in local `private/raw`; the tracked derivative records only the bounded findings needed for review.

## Environment and preconditions

Baseline `v0.2.0-experimental.6` at exact main `d03d0a855d32fbfb8b42c29db2f008263de0f806`. All files and payloads were synthetic under disposable temporary directories. No Muse data, Production system, credential, or private signing key was used.
