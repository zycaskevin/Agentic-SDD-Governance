# Reproduction

## Expected

Local path masking covers the native Windows forms of WSL UNC paths; multi-file redaction either publishes one complete call or removes only its owned outputs. Supported Darwin aliases are accepted without following caller-controlled symlinks. Source Green precedes packaging, and Broker shutdown drains both pipes while it waits.

## Actual

The R19 independent review reproduced unmasked `wsl.localhost` and `wsl$` UNC paths, an earlier redaction output surviving a later source failure, Darwin temporary-system collection rejection, build-before-source-validation ordering, and a wait-before-drain Broker subprocess boundary.

## Deterministic steps

1. Apply whole-buffer and five-byte streaming redaction to quoted and unquoted native WSL UNC fixtures and inspect the surviving local-path rule matches.
2. Redact a valid first source followed by symlink, disappeared, and forced-open failures; inspect the output directory and a synchronized replacement.
3. Inspect native workflow ordering and exercise collection under the Darwin system temporary alias.
4. Terminate a child that emits more than one pipe buffer to stdout and stderr.

## Environment and preconditions

R19 Gate Head `88212fc760aaf4b74a67826abc40de4632af5a29` on Linux aarch64 with Python 3.12; the Darwin path case requires hosted macOS-15.
