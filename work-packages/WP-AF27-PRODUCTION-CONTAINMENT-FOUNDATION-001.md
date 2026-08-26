# Work Package: AF27 Production Containment Foundation

## References

- Issue: [#54](https://github.com/zycaskevin/Agentic-SDD-Governance/issues/54)
- Predecessor: `WP-AF26-EXTERNAL-TRUSTED-RUNNER-001`
- SDD: `docs/TRUSTED_RUNNER_V0_2_AF27.md`
- Risk: L2 security-sensitive engineering; this package is offline-only.

## Objective Contract

- Outcome: add offline executable contracts for the Linux cgroup-v2
  descendant-containment and FD-bound-runtime primitives required by the
  Trusted Runner production design.
- Success: the held-runtime contract rejects scripts, link/permission/content
  drift and path replacement; the synthetic scope requires limits, exact-FD
  launch binding, kill, empty observation and removal in that order.
- Keep: `mode=production` remains a bootstrap-time hard deny. No service
  account, systemd unit, `/etc` or `/var/lib` provisioning, credential, Hermes,
  network, inference, deployment or Live UAT is in scope.
- Rollback: remove only AF27 primitives, contracts, tests and evidence; AF26
  rehearsal behavior and its production hard deny remain intact.

## Scope

- `src/sddgov/production_containment.py` offline contracts and synthetic model.
- Trusted Runner production hard-deny regression, AF27 documentation and
  offline synthetic tests.
- No production activation or caller-visible widening of authority.

## Claim

- Owner: 2026-08-26 authorized AF27 offline safety implementation and an
  independent sub-agent review.
- Builder: Codex.
- Status: in progress; no production authority has been granted or enabled.
