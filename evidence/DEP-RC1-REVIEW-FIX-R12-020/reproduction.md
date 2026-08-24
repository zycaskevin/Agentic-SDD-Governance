# Reproduction

## Expected

Every still-valid PR #33 finding is independently reproduced and fixed without weakening fail-closed controls. Broker framing rejects delayed trailing bytes before authority checks or nonce consumption; ledger capacity is rejected before full scan allocation; trusted-approver authority cannot be selected by the caller; macOS service identity, executable preflight, umask, and log retention are explicit; release jobs use a pinned interpreter; historical evidence claims remain exact; and the complete product candidate is one revertible commit directly above trusted Base.

## Actual

The exact CodeRabbit review of commit `4ea3b66f63f7e7df643465d7fe654b81b1335ebe` reported 11 inline findings and ten nitpicks. The focused 13-test Red run recorded 12 failures and four errors, including subtest errors, at the reviewed boundaries. It reproduced early acceptance of a complete first Broker record before delayed trailing bytes, nonce-set allocation before near-limit rejection, caller-selected trust authority, unguarded offline bundle examples, incorrect launchd group and missing umask/rotation/preflight, unpinned protected publication jobs, stale runtime dependencies/private APIs/CI exemptions, and inaccurate historical proof text.

## Deterministic steps

1. Start from exact reviewed PR #33 Head `4ea3b66f63f7e7df643465d7fe654b81b1335ebe` and apply only the R12 regression assertions.
2. Run the focused command preserved in `terminal--r12-red-tests.txt`; observe 12 failures and four errors across 13 targeted tests.
3. Use `git--r12-review-bindings.txt` to bind the formal review plus all 11 inline REST/GraphQL identities and ten review-body nitpicks to independently checked dispositions.
4. Build and test the corrected single-parent implementation `f1e1e32217b54d429b80e2a9eeb97291a5b5d9d4`; preserve the complete Local Green, package proof, and rollback transcripts.
5. Rehearse `git revert --no-commit` of that implementation at audit-only descendant `1f96aa22b40d23b486540a3d49087d7c226a22d3` and compare the entire non-audit tree with trusted Base.

## Environment and preconditions

Trusted Base is `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. The formal review is node `PRR_kwDOTx8IyM8AAAABKddt9Q`, REST review `4996951541`, submitted on PR #33 against the exact Head above. Inputs are synthetic or repository metadata only; no real credential, private key, patient/customer data, production action, privileged Broker installation, or public package publication is used.
