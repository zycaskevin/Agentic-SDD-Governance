# Fix Scope

## Smallest sufficient change

Strengthen the existing gates at their current module boundaries; do not replace SDG or add new human approval gates. Convert ambiguous inputs into exact machine-verifiable contracts, retain verified filesystem generations through use, and make incomplete state transitions visible and recoverable.

## Files or components in scope

- `autonomy.py`: exact authority-field consistency, forced-human category isolation, structured reopen enum, safe assumption reads, durable Operational Action integration.
- `ci_guard.py`: duplicate-key-rejecting YAML semantic validation.
- `evidence.py` / `redaction.py`: intermediate symlink and non-regular input rejection, artifact proof snapshot, pending transaction detection/cleanup, and bounded rollback of incomplete collect/redact output.
- `merge_gate.py` / `protected-files.yaml`: meaningful rollback checks and complete security-source protection.
- Governance Schema/templates, packaged copies, dependency lock, version, Changelog, Roadmap, and permanent regression tests.

## Explicit non-scope

Production operations, real Muse data, credentials, stable publication, arbitrary unknown-secret discovery, and changes to the approved L0-L3 authority model.

## Blast radius

The CLI request contract, signed L2 receipt reopen value, CI workflow inspection, Evidence filesystem behavior, external-action state schema, installed governance resources, and trusted verifier dependency set. Existing experimental.7 L2 receipts with free-form reopen prose must be reissued for experimental.8; L0/L1 routine commands remain autonomous.
