# Reproduction

## Expected

Necessary UAT is reserved for subjective Owner judgment. Machine-verifiable work is rejected from that category without prompting. Exit code 2 is unique to a validated ACTION_REQUIRED. Malformed or risk-downgraded durable rows fail before state/event mutation. A partially governed Base never enters first-consumer trust bootstrap. Bundled resource lookup works through the declared Python 3.10 floor.

## Actual

At exact Head `b815214632a820451d3e8444af9ebfea8a2ec0f5`, five independent P1 contracts failed: caller-only UAT bypass, exit-code ambiguity, post-write risk validation, incomplete first-consumer markers, and Python 3.10 Traversable incompatibility.

## Deterministic steps

Run the eight focused unittest cases recorded in `private/raw/terminal--final-coderabbit-red.txt`. Before the fix the matrix produced six failures and two errors: UAT returned CONTINUE, usage/process errors returned 2, malformed/downgraded rows mutated or crashed, installed-policy-only Base returned first-consumer true, and the one-child Traversable raised TypeError.

## Environment and preconditions

Fresh exact Head, Repo-local `PYTHONPATH=src`, synthetic temporary repositories and action stores, no network, credentials, Production data, or real user data.
