# Regression Evidence

## Regression test added or strengthened

- Native invariant: bound AF_UNIX fd and pathname are sockets but have different
  identities on Linux.
- Real subprocess reaches listen, answers exact health, handles SIGTERM, removes
  only its node, and restarts twice.
- First staging stat failure cleans only the exclusive staging node; synchronized
  final replacements survive and remain connectable.
- Linux `RENAME_NOREPLACE` / Darwin `RENAME_EXCL` publication never clobbers.
- Installed-wheel smoke repeats the native Broker health/cleanup contract.
- Merge/rollback audit windows reject illegal transient commit edges.

## Related tests executed

The isolated dual-lock environment ran 379 tests successfully. Six native tests
also passed outside the restricted sandbox with ResourceWarnings promoted to
errors. Validate, CI verify, and Local Gate passed. Hosted Linux/Darwin native
CI remains a required external gate before merge.

## Unaffected paths sampled

Receipt/autonomy, DEP lifecycle, redaction, service mirrors, release lock floors,
build/Twine, offline bundle, Codex/Hermes Doctor, demo, rollback exact-tree, and
Base installed-consumer paths passed. The rollback exercise ran 229 Base tests.
