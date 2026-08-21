# Root Cause Hypothesis

## Hypothesis

The review failures came from incomplete boundary contracts rather than one algorithmic defect: several reads/retries were checked only after unbounded work, release mismatches could skip jobs, protected-resource coverage and documentation had drifted, and Evidence media semantics changed without a schema-versioned compatibility boundary.

## Supporting evidence

The focused Red transcript fails at the exact affected APIs. The first rollback transcript proves the trusted Base cannot consume retroactively relabeled historical manifests. The second Red transcript proves the current verifier cannot simply retain those legacy labels without an explicit bridge. PR review REST/node IDs and exact paths are preserved in `git--r10-review-bindings.txt`.

## Contradicting evidence

The full current and trusted-Base suites otherwise remained Green, so the evidence does not support a broad redesign of autonomy classification, signature formats, exact-tree rollback, or redaction rules. CodeRabbit's docstring-coverage preference is not a demonstrated repository correctness defect.

## Falsification test

Add focused assertions for each reported boundary, including oversized/unterminated ledger records, repeated accept failures, permanent 403, exact release tag, package lock, source/resource parity, new versus legacy manifest versions, and rollback equality. The hypothesis is falsified if those assertions pass without the bounded fixes or if the final rollback cannot verify historical audit descendants.

## Conclusion

Confirmed. The bounded fixes make all focused/current tests Green; manifest schema 1.1 enforces accurate JSON labels for new Evidence while a narrow schema 1.0 compatibility rule preserves old proof; and the final one-commit rollback returns the non-audit tree exactly to Base and passes the Base verification matrix.
