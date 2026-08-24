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

`verify` checks the contract and automatic GitHub-hosted workflows. `local-gate`
first acquires one owner-only current-user coordination lock, then verifies those
controls, runs every configured local command sequentially, and stops on the
first failure. `local_green.command_timeout_seconds` applies an explicit bounded
deadline to each command. New templates set it to 600 seconds; schema `1.0`
contracts that omit it use the same bounded legacy fallback, so an existing
installation remains Green without allowing an unbounded command. Independent
Local Green invocations for the same POSIX user wait rather than execute
repository-controlled gates concurrently; the lock does not retry, skip, or
change any configured command.

Any `local-gate` failure starts or continues a DEP at Red. Capture the bounded
local failure, advance through Evidence → Fix → Green → Proof, and do not spend
another hosted run until the new revision is locally Green. A transient hosted
provider failure may be rerun only when the DEP evidence identifies it as such.

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

Draft skipping accepts either the exact legacy cross-event guard or a stricter
flat conjunction. A stricter conjunction must contain independent top-level
comparisons that bind `github.event_name` to the workflow's single PR event
family and require `github.event.pull_request.draft == false`. Disjunctions,
parentheses, functions, nested interpolation, incomplete comparisons, and
missing or mismatched event/Draft atoms fail closed.

`hosted.post_merge_verification` accepts only `manual_only` or `automatic`.
For schema `1.0`, an omitted field retains the legacy `automatic` behavior so
an existing governed repository has an explicit migration path. New installs
and upgraded repositories should add the field explicitly. When it is
`manual_only`, automatic `push` events are forbidden even for workflows listed
under `exempt_workflows`. Use the one non-Draft PR verification as the Work
Package's hosted run; keep `workflow_dispatch` for a deliberately requested
Release verification. A successful Merge must not silently consume a second
hosted run.

Schema `1.0` also permits an older `local_green` object to omit
`command_timeout_seconds`. Runtime verification and Local Green then use the
600-second fallback. New installs and deliberately updated configurations
should retain the explicit template value; invalid configured values still fail
closed rather than falling back.

Every `exempt_workflows` entry must be the exact filename of one workflow found
under `.github/workflows`; display names, globs, missing files, and duplicates
fail closed. Unlike `write_permission_exceptions`, a discovered but otherwise
unused workflow exemption is not rejected. Exemption is a narrow, auditable
mapping, not a pattern language.

Do not use path or commit-message skipping for a required check without coordinating branch protection: GitHub may leave the required check pending. Prefer one cheap required workflow and conditionally activated expensive jobs.

## Risk and authority

| Change | Level | Behavior |
|---|---:|---|
| concurrency, timeout, cache, Draft skip | L1 | Agent may implement and verify |
| test scope or required-check change | L2 | preserve acceptance criteria; request one decision |
| Billing budget or self-hosted runner | L3 | require explicit owner action |

CI savings never authorize weaker tests, deployment checks, evidence, or security controls.
