# Work Package: AF27 Production Containment Foundation

## References

- Issue: [#54](https://github.com/zycaskevin/Agentic-SDD-Governance/issues/54)
- Predecessor: `WP-AF26-EXTERNAL-TRUSTED-RUNNER-001`
- SDD: `docs/TRUSTED_RUNNER_V0_2_AF27.md`
- Risk: L2 security-sensitive engineering; this package is offline-only.

## Objective Contract

- Outcome: add the executable Linux cgroup-v2 descendant-containment and
  FD-bound-runtime primitives required by the Trusted Runner production design.
- Success: primitives fail closed on a non-v2/unwritable hierarchy, reject
  scripts and runtime identity drift, keep the verified runtime FD open through
  child launch, and have deterministic tests for setup, timeout cleanup and
  refusal paths.
- Keep: `mode=production` remains a bootstrap-time hard deny. No service
  account, systemd unit, `/etc` or `/var/lib` provisioning, credential, Hermes,
  network, inference, deployment or Live UAT is in scope.
- Rollback: remove only AF27 primitives, contracts, tests and evidence; AF26
  rehearsal behavior and its production hard deny remain intact.

## Scope

- `src/sddgov/trusted_runner.py` and `src/sddgov/_trusted_exec.py`.
- AF27 documentation, offline synthetic tests and Debug Evidence Package.
- No production activation or caller-visible widening of authority.

## Claim

- Owner: 2026-08-26 authorized AF27 offline safety implementation and an
  independent sub-agent review.
- Builder: Codex.
- Status: in progress; no production authority has been granted or enabled.
