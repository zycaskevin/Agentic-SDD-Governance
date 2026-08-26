# Reproduction

## Expected

The decision assumptions must contain one exact canonical Owner-client binding.

## Actual

The committed decision document contained zero matching marker lines, so the
Owner client failed closed before signer use or receipt creation.

## Deterministic steps

Count exact `Owner client binding: ` lines in the committed decision assumptions
and compare the result with the required value `1`.

## Environment and preconditions

Offline repository inspection and synthetic unit tests only. No signer, key,
receipt, trust-store content, or production data was collected.
