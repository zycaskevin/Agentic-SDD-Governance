# Issue: Reset SDG around real-world effects

Status: active

## Problem

The RC1 path applied high-assurance approval machinery before ordinary software
work produced a real-world effect. This made the product owner operate terminals,
signers, receipts, and review hand-offs that agents and deterministic checks
should have handled.

## Desired outcome

SDG stays invisible during development and release readiness. It interrupts the
owner only for one unresolved product-direction choice or one concrete action
that crosses a real-world effect boundary.

## Acceptance

- The product boundary is documented in plain language and machine-readable form.
- Development and release readiness allow zero owner operations.
- SHA-256 and exact Git references remain machine-only integrity data.
- Independent review remains agent-to-agent; the owner never relays findings.
- Merge is L3 only when repository configuration makes it trigger a real L3 effect.
- Strong authorization is retained only for a real effect with a distinct trust boundary.
- The old RC1 Broker and signing work is preserved but not a default dependency.

## Baseline inconsistency resolved locally

At Base `e2f9555ed9ba3acfa7425786968f5ff4e7c7ea5e`, the repository's own contract
suite still expects the intentionally removed `.agentic-sdd-governance/`
self-install and `.github/workflows/governance.yml`. This is a pre-existing
deactivation/test mismatch, not a reason to reinstall SDG. The product-reset
branch now verifies deactivation explicitly and retains temporary-project
Installer coverage instead of restoring the removed files.
