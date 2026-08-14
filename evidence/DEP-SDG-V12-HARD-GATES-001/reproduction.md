# Reproduction

## Expected

Unknown or dangerous actions cannot be authorized by a caller-provided L0/L1 label. An L3 approval must be owner-verifiable and consumed atomically. Merge requirements must be executed, not merely documented.

## Actual

At merged main `849c2be`, `delete_production_customer_data` with `risk_level=L1` returned `CONTINUE`. `decision authorize-operation --approved-by product-owner` accepted an unverified string, and repeated evaluations returned `CONTINUE` until a separate consume command ran. CI executed tests and `validate` but no merge-policy verifier.

## Deterministic steps

1. Initialize a team-standard state directory.
2. Evaluate `{\"risk_level\":\"L1\",\"category\":\"delete_production_customer_data\"}`.
3. Mint an approval with `decision authorize-operation` using only caller strings.
4. Evaluate the same L3 request twice without calling `consume-operation`.
5. Inspect `.github/workflows/governance.yml` and search for `merge verify`.

## Environment and preconditions

Clean GitHub clone at merge commit `849c2becd9104c65dedd6d84533f8986db02f7e1`; no Production access, credentials, or external data involved.
