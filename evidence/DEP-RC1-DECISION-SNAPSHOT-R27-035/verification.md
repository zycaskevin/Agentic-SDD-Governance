# Verification

## Green command and result

- Focused security/authority/CI set: 159 tests, 158 PASS, one expected AF_UNIX
  sandbox skip.
- Complete sandboxed suite: 528 tests, 514 PASS and 14 expected platform/sandbox
  skips.
- Host Local Green from the fixed repository audience: 528 tests, 523 PASS and
  five platform-only skips; repository validation PASS; exact Owner product
  decision verification PASS.
- `python -m sddgov.cli validate .`: PASS.
- `python -m sddgov.cli ci verify .`: PASS.
- Merge Gate and reviewer unit suites: 56 PASS.
- Owner receipt SHA-256
  `bfec7d143aace88f37d5d5cf3970c61b797c8754c64e3819e31fd66c6c1dfbe9`:
  signature, stored row, repository audience, trust domain, expiry, exact request,
  assumptions, summary, validity, and current Owner-client identity all PASS.
- Candidate wheel and sdist build plus Twine: PASS.  Wheel SHA-256
  `01a66fa0e0b7cc1bd5ef9f6c40ebf103c59de2caae69faf97390506516403d58`;
  sdist SHA-256
  `eac589e4f7073710de960f307fde881ef07e23da230422608e348492d98804b9`.
- Final offline bundle: PASS with ten dependency wheels and four public assets.
  Fresh-wheel smoke imported no source checkout, verified 13 bundle files/12
  payload files, validated Codex and Hermes installations with 73 managed files
  each, and passed the quick demo plus real Linux AF_UNIX rehearsal.
- Actual declarative rollback of
  `06e528d39fcbb156ed7352bd4e0e40b2b2698a33`: PASS.  The reverted non-audit
  tree exactly matched trusted Base, setup/Doctor/validate passed with 66 managed
  files, and the Base suite passed 237 tests with one sandbox skip.  Base wheel
  and sdist build plus Twine also passed.

## Before/after evidence

R26 returned 307200 cached bytes under a later 262144-byte limit.  R27 raises a
bounded `ValueError`.  R26 verified signed inputs through separate snapshots;
R27 passes one retained snapshot into the single envelope verification and its
context exit rejects a substituted assumption generation.

## Remaining limitations

The R27 Owner-client source identity is
`2bd8ea9fdeec596feb0997f36ddb0f189394e7fa392a64b6a19bb4d06fd997d2`.
The fresh Owner A decision is imported and locally reverified.  This Proof does
not self-authorize merge: hosted Linux/macOS Green, final CodeRabbit review, the
trusted-Base Gate digest, and a fresh independent reviewer receipt remain
separate mandatory merge conditions.
