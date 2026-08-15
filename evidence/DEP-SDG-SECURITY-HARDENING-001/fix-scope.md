# Fix Scope

## Smallest sufficient change

Move PR verification to a base-controlled `pull_request_target` workflow with separate candidate and trusted-verifier checkouts; make Evidence paths and manifests executable integrity contracts; replace unsigned L2 recording with signed import; and bind L3 approval to an exact canonical operation payload.

## Files or components in scope

- `.github/workflows/governance.yml` and CI Cost Guard workflow inspection.
- `src/sddgov/evidence.py`, `redaction.py`, `autonomy.py`, `merge_gate.py`, and `cli.py`.
- Evidence, decision, and operation receipt schemas/templates.
- Adversarial and compatibility tests.
- Hard-gate, Evidence, installation, adapter, Changelog, Roadmap, and package-resource copies.
- Disposable synthetic Muse pilot fixtures and runner.

## Explicit non-scope

Production systems, real Muse data, private signing keys, Billing, hosted runner provisioning, unrelated collector feature expansion, and stable-release publication.

## Blast radius

High within the governance package because schemas and CLI contracts change; bounded outside it because no governed product, Production environment, credential, or real Evidence source is touched. Existing experimental decision records require explicit migration to signed L2 envelopes.
