# Verification

## Green command and result

PASS: exact boundary-to-Base tree equality; actual atomic revert; zero non-Evidence/non-audit difference from Base; reconciled Doctor; reverted full tests; current candidate 221 tests and Local Green; DEP-013 full and portable strict verification.

## Before/after evidence

Before: the selected rollback removed only the second fix increment and could not satisfy Merge verification. After: boundary `27f860484b2604d83d80e364eb9ca33eccfcd191` equals Base outside Evidence/audit, and atomic implementation `2d8497efe36f394637f8a224c70a32167f69bbd5` restores the complete candidate in one reversible unit.

## Remaining limitations

Portable DEP cannot independently prove untracked raw bytes. Final security re-review, signed Review receipt, one hosted verification, GitHub Ruleset/security-control activation, Merge, signed/attested build, and Release remain separate gates.
