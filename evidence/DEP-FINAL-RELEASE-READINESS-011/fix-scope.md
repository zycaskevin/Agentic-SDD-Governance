# Fix Scope

## Smallest sufficient change

Add exact executable contracts for classifier exit status, Decision Package binding, signed durable external-action resolution, immutable first-consumer policy/trust, portable Proof migration, and structured invalid exemption handling.

## Files or components in scope

`autonomy.py`, `governance.py`, `merge_gate.py`, `ci_guard.py`, `cli.py`; canonical and packaged Policy/Schema/Skill/templates/docs; protected inventory; tests; three legacy DEP association records.

## Explicit non-scope

GitHub Rulesets and security settings, Billing, credentials, Production, public Release creation, real user data, and any expansion of L2/L3 authority.

## Blast radius

Classifier callers must handle nonzero exit codes; external-action CLI now uses `queue|resolve`; first-consumer bootstrap requires a one-time root-controlled public trust file. Routine L0/L1 behavior and already-governed Base verification remain unchanged.
