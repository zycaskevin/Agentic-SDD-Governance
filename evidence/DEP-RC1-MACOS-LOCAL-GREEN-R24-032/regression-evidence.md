# Regression Evidence

## Regression test added or strengthened

- Autonomy synthetic repository roots use the shared fixed Darwin alias canonicalizer before mocked Git top-level and trust-domain comparisons.
- Broker authority-store tests use the same canonical temporary repository root.
- Owner approval and synthetic distribution fixtures derive all venv, repository, and trust-domain paths from one canonical root.
- The bare-Python CI guard test uses a private retained runtime root, so it still proves interpreter substitution without contending with a top-level Local Green lock.

## Related tests executed

The affected autonomy, Broker, and Owner approval matrix ran 147 tests with 4 expected skips and no failures. The complete candidate-plus-Evidence suite ran 523 tests with 14 expected platform/sandbox skips and no failures. In the externally bound canonical repository, the configured Local Green ran the same 523 tests with 5 expected skips, repository validation, and exact stored product-decision verification; all commands returned zero and the decision verifier reported `SIGNATURE_ROW_AUDIENCE_AND_REQUEST_VERIFIED`.

## Unaffected paths sampled

Production `canonicalize_platform_path`, trust-domain equality, Owner source identity, the fixed public trust loaders, request/Decision Contract bytes, receipt digest, and every production lock path were unchanged. The Owner receipt remains `fb01428e4f296be43639fc4494844d964619adc263ac42253fea1ff563806337`, expires `2026-09-22T15:55:57Z`, and did not require another signature.
