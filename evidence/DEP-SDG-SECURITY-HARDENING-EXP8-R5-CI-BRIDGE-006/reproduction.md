# Reproduction

## Expected

The Base-controlled hosted verifier accepts a safe migration record without executing candidate-defined code, and candidate verification independently accepts the same record only through an exact legacy allowlist.

## Actual

Run `31919258947` reached `Enforce exact Merge policy` and exited 2 with `rollback record is missing or incomplete`; every trusted-checkout prerequisite succeeded.

## Deterministic steps

1. Use Base `f44cb5f` as the trusted verifier for PR #12.
2. Select `evidence/DEP-SDG-SECURITY-HARDENING-EXP8-R2-002/rollback.md`, which is declarative v2.
3. Run hosted `merge verify --skip-local-checks`.
4. Observe the Base v1 parser reject the v2 record before other Merge proof.

## Environment and preconditions

GitHub Actions `pull_request_target`, exact PR Head `57aadaf`, public trusted-reviewer variable present, no Production data or credentials.
