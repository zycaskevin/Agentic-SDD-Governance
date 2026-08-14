# Fix Scope

## Smallest sufficient change

Add machine-executable Reviewer bootstrap, public-trust export, and exact-gate signing commands, plus an on-demand independent Reviewer playbook for Codex and Hermes.

## Files or components in scope

`src/sddgov/reviewer.py`, CLI routing, targeted security tests, Skill reference, Codex/Hermes adapters, Hard Gates/User/Installation docs, packaged resource parity, Work Package, Changelog, Roadmap, and DEP proof.

## Explicit non-scope

No Production operation, L3 owner-approver provisioning, Billing change, deployment, branch-protection mutation, private key generation in the Builder workspace, or automatic Merge.

## Blast radius

The new commands are opt-in for an explicitly assigned independent Reviewer. Private keys are forced outside the Repo, created without overwrite, never printed, and required to be owner-only. Existing Merge verification and L0/L1 autonomy behavior remain unchanged.
