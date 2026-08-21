# Fix Scope

## Smallest sufficient change

Bind release inputs before publication, copy verified install inputs to a private
single-link snapshot, split Broker read/send deadlines, make redaction cleanup
generation-safe, close collection after redaction, and tighten only the validation
and documentation gaps demonstrated by Red.

## Files or components in scope

- Release bundle preparation, fresh-wheel smoke, and manual publish workflow.
- Broker normalization, response deadline, explicit serve dispatch, runbook, and
  reviewed Linux service hardening templates.
- Redaction marker streaming and failed-publication reconciliation.
- Evidence collection lifecycle, installer source detection, CI schema/runtime
  validation, quick pilot validation, README/guide portability, and CI guidance.
- Central merge-gate audit path classification, regression tests, release-tool
  dependency lock, and installed-governance resource/manifest parity.

## Explicit non-scope

- No TestPyPI, PyPI, GitHub Release, tag, Production, payment, credential, root
  service installation, or real Broker nonce consumption.
- No self-issued independent review receipt and no weakening of protected-file,
  exact-Head, exact-tree rollback, or trusted-base requirements.
- No affected-path rollback optimization, ledger cache, GPG trust root, mock
  Broker, or external review-thread replies/resolution.

## Blast radius

Release packaging and security-boundary code are sensitive, but the changes stay
inside existing fail-closed contracts. Compatibility risk is concentrated in
lock parsing, wheel/sdist metadata, Unix descriptors, and managed-resource parity;
focused adversarial tests, full Local Green, package build, fresh-wheel smoke, and
rollback proof cover those paths.
