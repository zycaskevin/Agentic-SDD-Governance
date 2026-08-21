# CI Cost Guard

CI Cost Guard keeps independent cloud verification while preventing an Agent from treating GitHub-hosted Actions as a remote debugger.

## Required loop

```text
change -> targeted local checks -> full local Green Gate -> bounded Push
       -> one current cloud run -> proof or DEP -> next change
```

The same revision may be rerun only when evidence identifies a transient runner, network, or provider failure. A code, test, migration, or configuration failure requires a local reproduction and a new revision.

## Contract

From an installed governed repository, copy `.agentic-sdd-governance/templates/CI_COST_GUARD.json` to `.sddgov/ci-cost-guard.json`, then replace the local commands and expected minutes for the repository. Commands are argument arrays and are executed without a shell.

```bash
sddgov ci verify .
sddgov ci local-gate .
```

`verify` checks the contract and GitHub-hosted workflows. `local-gate` first verifies those controls, then runs every configured local command sequentially and stops on the first failure.

## Workflow controls

All hosted workflows must declare concurrency and per-job timeouts. Automatic
hosted workflows must additionally cancel stale runs. Pull-request workflows
must avoid allocating runners for Draft PRs. Every workflow must declare
read-only default permissions.

Release jobs that require OIDC or GitHub Release publication must use
`workflow_controls.write_permission_exceptions` to name the exact workflow,
job, and write-capable permission. The verifier rejects unknown jobs, unused
exceptions, and any other write permission. Do not exempt the whole release
workflow: that also disables its timeout, concurrency, and permission checks.

`hosted.post_merge_verification` accepts only `manual_only` or `automatic`.
For schema `1.0`, an omitted field retains the legacy `automatic` behavior so
an existing governed repository has an explicit migration path. New installs
and upgraded repositories should add the field explicitly. When it is
`manual_only`, automatic `push` events are forbidden even for workflows listed
under `exempt_workflows`. Use the one non-Draft PR verification as the Work
Package's hosted run; keep `workflow_dispatch` for a deliberately requested
Release verification. A successful Merge must not silently consume a second
hosted run.

Do not use path or commit-message skipping for a required check without coordinating branch protection: GitHub may leave the required check pending. Prefer one cheap required workflow and conditionally activated expensive jobs.

## Risk and authority

| Change | Level | Behavior |
|---|---:|---|
| concurrency, timeout, cache, Draft skip | L1 | Agent may implement and verify |
| test scope or required-check change | L2 | preserve acceptance criteria; request one decision |
| Billing budget or self-hosted runner | L3 | require explicit owner action |

CI savings never authorize weaker tests, deployment checks, evidence, or security controls.
