# Root Cause Hypothesis

## Hypothesis

The R2 implementation solved the first review round but still composed release,
CI, Broker, demo, redaction, and documentation controls at boundaries that were
individually plausible and collectively weaker than the declared fail-closed
contract.

## Supporting evidence

- The preflight credential was repository-scoped and injected before the
  environment contract it was intended to inspect.
- `exempt_workflows` replaces all workflow controls with an empty mapping.
- Socket timeouts were per-read, not total-request, and cleanup identity was
  captured after fallible post-bind operations.
- Quick Demo copied only selected nested fields; the nested verdict and portable
  proof were not part of its final conjunction.
- Whole-buffer private-key regexes accept a marker across `\n`, but the
  streaming implementation called them one logical line at a time.
- Installation prose described a py312 artifact while selecting generic
  `python3`, first-match files, and an unqualified later CLI.

## Contradicting evidence

- R2's 257 tests, strict DEP, package build, and fresh-wheel smoke were genuine
  and remain useful; the issues occur in missing adversarial boundary cases.
- The old `DEP-RC1-READINESS-008` redaction report accurately hashes a zero-byte
  terminal capture. Its filename is misleading, but it is not the oversized
  synthetic source itself and must not be rewritten into a fictitious record.
- The old DEP rollback targets its original implementation commit. It is not the
  rollback contract for the superseding R2 or R3 reviewed stack and remains
  immutable historical evidence.

## Falsification test

Require adversarial regressions for slow partial reads, post-bind failures,
nested FAIL verdicts, cross-line PEM markers, exact permission exceptions,
manual-workflow concurrency, exact artifact counts, and interpreter identity;
then run full tests, validation, Doctor, package/fresh-wheel smoke, and a
disposable exact-Base rollback drill from the R3 implementation commit.

## Conclusion

The hypothesis is supported. The smallest sufficient correction is a new clean
R3 history with one atomic implementation commit and a new DEP/Gate; mutating
R2's Gate descendants or old DEP content would destroy the audit meaning of the
previous review.
