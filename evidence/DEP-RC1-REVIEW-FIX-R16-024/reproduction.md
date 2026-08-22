# Reproduction

## Expected

The native matrix must reach the Broker's publication, health, cleanup, race,
and restart boundaries on both Linux and Darwin from the installed candidate
wheel. Test scaffolding must stay inside Darwin's AF_UNIX pathname limit while
the fixed production staging path is checked independently.

## Actual

PR #37's Linux job passed. Its macOS-15 job raised `OSError: AF_UNIX path too
long` at `server.bind(staging_path)` in five of six tests. The only passing test
bound the shorter direct identity pathname. The workflow set `PYTHONPATH=src`,
so even a Green run would not have proved installed-wheel provenance.

## Deterministic steps

1. Resolve PR #37 exact Gate Head `a4febd560a35bc7908fd0dcda54cbf5d0d471e70`.
2. Inspect hosted run `32549653876`: Ubuntu passes; macOS-15 fails at the nested
   staging bind with `AF_UNIX path too long`.
3. Use `/tmp/sgb-*` for native temporary roots and assert the fixed production
   Darwin staging path is at most 103 encoded bytes.
4. Build the wheel under both hash locks, install it into a fresh venv, clear
   source import paths, and execute the real native test script.
5. Require hosted Ubuntu and macOS-15 installed-wheel jobs before review.

## Environment and preconditions

Red is PR #37 against Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`.
Green is single-parent R16 product commit
`c17508e16c5e773ca457e291cc2f7355ccdf65f8`. Local native exercises used
short disposable owner-only directories and no real approval, nonce, customer,
patient, or payment data.
