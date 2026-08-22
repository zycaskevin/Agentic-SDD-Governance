# Reproduction

## Expected

The Broker must reach `listen()` on native Linux and Darwin, publish only when
the final pathname is absent, remove only entries it owns, preserve a competing
replacement, and restart cleanly. Tests must exercise the candidate server and
installed wheel with real AF_UNIX syscalls.

## Actual

PR #36 took `os.fstat(server.fileno())` and required that identity to equal the
bound pathname's `lstat()`. A real Linux socket returned two socket objects with
different device/inode pairs, so the candidate raised before `listen()` and left
the pathname behind. A class-level mock forced those identities to match.

## Deterministic steps

1. Bind a real AF_UNIX pathname socket on Linux.
2. Compare `fstat(fd)` with `lstat(path)` and confirm both are sockets but the
   identities differ.
3. Run the exact PR #36 server core and observe its pre-listen failure.
4. Run R15 native tests for health, signal cleanup, restart, first-stat failure,
   final-path replacement, and no-clobber publication.
5. Repeat from the freshly built installed wheel and on hosted Linux/Darwin CI.

## Environment and preconditions

Red is bound to PR #36 reviewed Head
`93e4eed7a811aaa3d195a80c789468349add0292` and Base
`1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. Green is the single-parent R15
product commit `d2a3632a8e281552ac117a5b7db47fa73cb8f29f`. The Linux
reproduction used a disposable owner-only temporary directory and no authority
state or production data.
