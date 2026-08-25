# Verification

## Green command and result

The recorded focused unittest command passed 88 tests. `sddgov validate .`
also passed.

## Before/after evidence

Before: unrelated AF27 changes necessarily ran R22. After this offline change:
the pure classifier can distinguish exact AF27-only paths, but the configured
Gate remains unconditional until a later approved activation.

## Remaining limitations

The classifier has no trusted-Base diff executor yet. It must not be enabled
until a separate L2 decision, protected-file review, and an implementation
that derives paths from the trusted Base are complete.
