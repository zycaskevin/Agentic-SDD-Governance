# Reproduction

## Expected

Existing schema `1.0` repositories that omit the newly introduced
`local_green.command_timeout_seconds` remain bounded and pass `ci verify` after
`setup-agent --force`; explicit invalid values remain rejected. A workflow
listed in `exempt_workflows` skips the full concurrency control promised by the
documentation. Every Git operation used to construct a large synthetic
Monorepo fixture uses the computed scaled setup timeout.

## Actual

The exact R27 Gate rejected a preserved legacy configuration because the new
timeout field was required with no runtime fallback. It also validated a
malformed concurrency group for an exempt workflow, called 600 seconds a
managed default when only the templates supplied it, and let the later fixture
Git operations fall back to 180 seconds while the 50,000-file setup advertised
750 seconds.

## Deterministic steps

1. On exact Gate `d1aec48e8896f0da3cb3c7733e66787f0f3671bc`, remove only
   `local_green.command_timeout_seconds` from an otherwise valid schema `1.0`
   contract, run `setup-agent --force`, and confirm the contract bytes are
   preserved.
2. Run `sddgov ci verify`; observe the timeout-field validation error.
3. Mark a discovered workflow exempt, leave a blank concurrency group, and run
   `verify_guard`; observe the concurrency-group error despite the exemption.
4. Inspect or mock the Monorepo benchmark's `_git` calls after the initial bulk
   commit; observe that they omit the computed `setup_timeout`.
5. Compare the canonical and packaged CI Cost Guard documentation with the
   runtime behavior.

## Environment and preconditions

Public PR #51, exact CodeRabbit review `5004444722`, Python 3.12, Linux. The
locally redacted review/reproduction record is
`shareable/artifacts/terminal--r28-code-review-red.txt`; it contains no raw
credential, private key, production data, or user path.
