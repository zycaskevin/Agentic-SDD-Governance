# Root Cause Hypothesis

## Hypothesis

The review failures came from incomplete boundary contracts rather than one algorithmic defect: Broker deployment assumed an avoidable privileged ownership mutation and did not pin the platform group or active-ledger capacity; CI exemptions were compared only loosely; release and Evidence cleanup did not preserve the primary failure in every path; and documentation overstated or omitted platform/proof constraints.

## Supporting evidence

The focused Red transcript fails at the exact affected APIs and service contracts. PR review REST/node IDs, exact paths, and verified dispositions are preserved in `git--r11-review-bindings.txt`. The stale-output redaction assertion demonstrates that publication before final source identity validation leaves observable residue, while release helper assertions demonstrate recursive parent creation and cleanup error masking.

## Contradicting evidence

The current and trusted-Base suites otherwise remain Green, so the evidence does not support weakening the Hard Gate, changing autonomy risk from the policy-defined L1 engineering scope to L3, adding a mock Broker, or replacing exact-tree rollback with affected-path-only comparison. CodeRabbit's remaining docstring and template preferences are not demonstrated correctness defects.

## Falsification test

Add focused assertions for exact socket ownership/mode/group, already-correct ownership without `chown`, wrong service group, active-ledger scan and append caps, exact workflow exemption use, final-component-only directory creation, primary-error preservation, launchd throttling, directory cleanup diagnostics, and post-publication redaction reconciliation. The hypothesis is falsified if these assertions pass on the reviewed Head without the bounded fixes, or if the corrected candidate cannot pass package proof and exact-tree Base rollback.

## Conclusion

Confirmed. Those assertions reproduce the defects on the reviewed Head and pass after the bounded corrections. The final current suite, source validation, package proof, and actual rollback drill are Green. The rollback returns the non-audit tree exactly to Base, retaining only Evidence, Merge Gate, and review audit descendants.
