# Reproduction

## Expected

Experimental.8 must fail closed when a low-risk envelope carries a concrete target, parameters, nested authority, or sensitive operation. CI policy must validate actual YAML semantics from repository-owned regular files. Evidence/Redaction must reject non-regular inputs promptly, publish only an exact verified generation, and never overwrite a later writer.

## Actual

The first candidate returned `CONTINUE` for equivalent sensitive intent that escaped free-text heuristics. CI accepted an always-true `if` expression and linked workflow paths. Redaction could block on FIFO input. Evidence control and attachment publication had check/use windows, partial-failure cleanup gaps, and destructive rollback paths. Rollback prose accepted wrappers or observational commands, and protected inventory omitted policy-bearing sources.

## Deterministic steps

1. Evaluate bounded L1 requests with concrete or nested Production/destructive/credential parameters.
2. Verify synthetic workflows containing an always-true Draft-condition disjunction, invalid runner/concurrency values, duplicate YAML 1.1/1.2 keys, and linked workflow parents/leaves.
3. Replace a manifest-covered raw artifact with a FIFO and invoke redaction under a two-second subprocess timeout.
4. Inject failures and later-writer replacements before and after raw/shareable/control publication.
5. Rewrite verified control bytes without changing inode, size, or mtime, then attempt attachment publication.
6. Submit free-form rollback wrappers/no-ops to the Merge verifier.

## Environment and preconditions

Baseline candidate `b323b832d56a35138172e7f51b76abcbda1d7fe7` on `fix/security-hardening-exp8`; macOS; Python 3.14.3. All probes use synthetic local data, no credentials, no network authority, and no Production resource.
