# Reproduction

## Expected

Release environment preflight must reject any incomplete or additional deployment policy inventory. Release file checks must validate the expanded path. Fresh-wheel smoke must run installed managed-tree `validate` for both supported adapters. The Broker must start on Linux without unsupported socket chmod flags and return once one bounded newline-terminated request is complete. Suspect private-key delimiters split across logical lines must never reach shareable output. A source checkout demo must execute the checkout's code, not an unrelated globally installed SDG version. Review Evidence must retain stable review nodes and exact inline URLs.

## Actual

The R4 review found 8 actionable defects and 9 nitpicks. Direct Red tests showed a `total_count` mismatch was accepted, `~/synthetic.whl` failed before validation, the smoke harness did not call `validate`, and a partial private-key delimiter was published unchanged. A Linux probe showed socket `chmod(..., follow_symlinks=False)` could not complete. A clean-clone demo then selected an older installed CLI and failed with parser exit 2 even though the newly built wheel passed its pilot.

## Deterministic steps

1. Validate an environment response whose `total_count` is two but whose first page contains only the exact RC tag.
2. Pass `~/synthetic.whl` to the fresh-wheel regular-file helper under a controlled `HOME`.
3. Inspect and run the fresh-wheel harness for installed `validate` after Codex/Hermes setup.
4. Send a complete newline-terminated Broker request without closing the write side; separately exercise the size limit and the real path chmod call.
5. Redact `----`, newline, `-BEGIN PRIVATE KEY-----`, a synthetic body, and a normal end marker; confirm no output is published.
6. Run `demo/run.sh` from an exact implementation clone without a clone-local virtual environment while an older `sddgov` exists on `PATH`.
7. Resolve PR 25 and PR 26 review nodes and record every inline `discussion_r...` URL as the authoritative binding.

## Environment and preconditions

Trusted Base is commit `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`, tree `7b48daf1558a6ca3e02f20654663292a39772fce`. R5 is one single-parent implementation commit `05822d004e84c13d4e5bc6e3967e798b675348ed`, tree `a45f863785de71d6af39705401b482b9ec4e6aab`. Tests use only synthetic values; no real key, credential, user data, Production operation, registry upload, or privileged service is present.
