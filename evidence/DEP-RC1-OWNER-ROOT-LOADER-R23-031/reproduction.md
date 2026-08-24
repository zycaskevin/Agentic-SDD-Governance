# Reproduction

## Expected

After the protected Owner runtime passes isolation checks, it should load the fixed public trust data, build the exact A/B card, and stop before signing until the Owner chooses. Agent-side verification must continue to reject root execution.

## Actual

The Owner CLI returned its bounded fail-closed error. Read-only stage diagnostics reported runtime PASS followed by card FAIL; the signer and outbox stages were not reached, and no receipt existed.

## Deterministic steps

1. Install the reviewed R22 preview wheel into the root-owned isolated Owner venv.
2. Provision the fixed public trust documents, Owner signer socket, and one-way outbox through the separately approved L3 ceremony.
3. Run the non-signing root diagnostic for `_require_owner_runtime`; observe PASS.
4. Run the non-signing card diagnostic; observe failure at trusted public-key loading.
5. Inspect the call path from `build_product_approval_card` to `_trusted_approver` and `load_control_plane_json`; confirm the Agent loader rejects effective UID zero before reading the valid fixed file.

## Environment and preconditions

Baseline is exact preview `ede4e754fa779c822cf4051c834141cdfb058f88` on Linux/Python 3.12. Public trust and signer provisioning had already passed its reviewed L3 ceremony. Diagnostics were fixed-code, read-only, and did not render a card, contact the signer, read private key material, or write a receipt.
