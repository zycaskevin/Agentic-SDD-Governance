# Fix Scope

## Smallest sufficient change

Replace caller trust with canonical action/effect classification, trusted Ed25519 receipt import with atomic consumption, and an executable Merge verifier invoked by CI.

## Files or components in scope

`autonomy.py`, `merge_gate.py`, CLI, governance initialization, workflow, Schemas, Policy, Skill route, packaged resources, tests, documentation, version, Changelog, and Roadmap.

## Explicit non-scope

No Production operation, private signing key, GitHub ruleset mutation, Billing change, deployment, broader Agent orchestration engine, or native collector implementation.

## Blast radius

Existing projects gain one empty trusted-public-key store and additional managed governance resources. Routine canonical L0/L1 categories remain autonomous. L3 callers must migrate from string authorization to signed receipts, and PRs must provide a Merge gate receipt.
