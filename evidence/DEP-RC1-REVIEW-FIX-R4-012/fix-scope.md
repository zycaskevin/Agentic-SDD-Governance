# Fix Scope

## Smallest sufficient change

Preserve the RC1 architecture and fix only the reviewed contract gaps: tolerate an inner Pilot failure long enough to render it; derive quick-demo verdicts from one required-check mapping; isolate evaluation and pip environments; use original-text regex indices; align rollback audit descendants; constrain schema property names; synchronize canonical/package/install resources; clarify onboarding, rollback, and architecture limitations; and add focused regressions.

## Files or components in scope

`demo/run.sh`; `src/sddgov/{pilot,redaction,merge_gate}.py`; `scripts/fresh_wheel_smoke.py`; CI schemas and installed manifest; Rollback/Roadmap/Traditional Chinese onboarding docs; RC1 Work Package; and targeted demo, pilot, redaction, Broker, release-bundle, CI, repository-contract, and Merge-gate tests.

## Explicit non-scope

No change to action risk classification, signatures, Owner keys, L3 nonce consumption, production Broker installation, release publication, GitHub environments/rulesets, exact-tree rollback equality, historical R3 Evidence, or independent Reviewer authority. No TestPyPI/PyPI/GitHub Release action is authorized.

## Blast radius

Local developer and verification behavior only. Security-sensitive changes are fail-closed: unknown descendants remain rejected; only `evidence/`, `.sddgov/merge-gate.json`, and `.sddgov/reviews/` are audit descendants; redaction retains its size/marker limits; and fresh-wheel installation remains offline and hash-locked.
