# Root Cause Hypothesis

## Hypothesis

The root Owner client and non-root Agent verifier had incompatible identity policies because both used `load_control_plane_json`. The Owner runtime correctly required effective UID zero for its protected installation and outbox, while the Agent loader correctly rejected effective UID zero because a root Agent is not independent from a root-owned trust store.

## Supporting evidence

- The reviewed root diagnostic returned `OWNER_DIAGNOSTIC_CARD_FAIL` after runtime isolation passed.
- A bounded card-stage diagnostic and static call-path review localized failure to trusted public-key loading before any signer or output operation.
- `load_control_plane_json` unconditionally rejects effective UID zero.
- `sddgov-owner` and its outbox contract deliberately require a root-owned, root-executed runtime.

## Contradicting evidence

The same installed wheel built the card successfully for a non-root process, and the Agent loader's existing root-refusal test passed. This rules out malformed request, trust JSON, repository binding, or package corruption and isolates the defect to using the wrong identity-specific loader.

## Falsification test

Keep the Agent loader unchanged; add a root Owner-only loader that accepts exactly the two fixed public trust paths and reuses the complete descriptor-bound control-plane reader. The hypothesis is falsified if a root Owner card still fails, a non-root caller can use the Owner loader, a caller-selected path is accepted, or any Agent verification path uses the Owner loader.

## Conclusion

Confirmed. The defect was an identity-routing conflict, not missing trust data or signer availability.
