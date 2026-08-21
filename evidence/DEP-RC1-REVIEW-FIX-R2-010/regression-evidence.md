# Regression Evidence

## Regression test added or strengthened

- `test_service_signals_remove_only_the_bound_socket_and_allow_restart` raises
  both `SIGTERM` and `SIGINT`, proves identity-bound cleanup, handler
  restoration, and immediate restart.
- Release-bundle tests require an exact manifest, locked dependency wheelhouse,
  project-wheel digest match, non-symlink root, and tamper rejection.
- Release-environment tests require a nonempty reviewer set, self-review and
  administrator-bypass prevention, custom policies only, and one exact tag.
- The benchmark CLI test proves `--threshold-seconds inf` is rejected at parse
  time; the threshold is verifier-owned.
- Redaction tests cover over-limit logical lines with and without a final
  newline and prove no output is published. Streaming-rule selection is by
  rule identity, not tuple position.
- Repository contracts cover demo prerequisites/signals, machine-only key
  ceremony, protected release scripts, offline bundle use, historical Gate
  invalidation guidance, and packaged/installed parity.

## Related tests executed

- `.venv/bin/python -m unittest discover -s tests -v`: 257 passed, two skipped
  because this execution sandbox forbids native Unix socket creation.
- `.venv/bin/sddgov validate .`: PASS.
- `.venv/bin/sddgov doctor .`: PASS, Codex `team-standard`, 71 managed files.
- Twine checked the new wheel and sdist; fresh-wheel smoke verified 12 bundle
  files, installed ten locked runtime wheels without an index, ran Codex and
  Hermes Doctor, and passed the offline quick demo.
- A disposable revert of the old implementation made the old Gate exit 3 for
  an exact reviewed-Head mismatch.

## Unaffected paths sampled

- Existing autonomy signatures, L3 nonce/replay, Runtime Context, Base-trusted
  verifier, exact-tree rollback, evidence TOCTOU/symlink/hardlink, installer,
  governance queue, CI cost guard, reviewer signing, and synthetic pilot suites.
- Canonical, packaged-wheel, and currently installed governance resources.
