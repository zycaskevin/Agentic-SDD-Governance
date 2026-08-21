# Reproduction

## Expected

Every still-valid PR #32 finding is independently reproduced and fixed without weakening fail-closed controls. Broker ownership, group, readiness, ledger capacity, and daemon retries are bounded; CI exemptions identify exact discovered workflow files; release and Evidence publication remain transactional; platform and prior-proof claims match demonstrated support; the candidate remains exactly reversible.

## Actual

The exact CodeRabbit review of commit `4d84760eec736f51e7e9a8a1c6edf9d912fb2ccc` reported 10 inline findings and six nitpicks. The focused 12-test Red run recorded six failures and nine errors at the reviewed boundaries, including a privileged `chown` dependency, platform-group drift, unbounded active ledger growth, inexact workflow exemptions, recursive directory creation, cleanup masking, launchd restart pressure, directory cleanup error leakage, and stale redaction output.

## Deterministic steps

1. Start from the exact reviewed R10 Head `4d84760eec736f51e7e9a8a1c6edf9d912fb2ccc` and apply only the R11 regression assertions.
2. Run the focused command preserved in `terminal--r11-red-tests.txt`; observe exit 1 with six failures and nine errors across 12 targeted tests.
3. Use `git--r11-review-bindings.txt` to bind the formal review and every inline REST/node ID to an independently checked disposition.
4. Build and test the corrected single-parent implementation `c49c46e2d07a328636461bda8106b65326f25507`; preserve the complete Local Green, package proof, and rollback transcripts.
5. Rehearse `git revert --no-commit` of that implementation at its audit-only descendant and compare the entire non-audit tree with trusted Base.

## Environment and preconditions

Trusted Base is `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. The review is PR #32 formal review `4996601150` at the exact R10 Head above. Inputs are synthetic or repository metadata only; no real credential, private key, patient/customer data, production action, privileged Broker installation, or package publication is used.
