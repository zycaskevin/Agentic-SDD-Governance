# Verification

## Green command and result

`PYTHONPATH=src python -m pytest tests/ -q` completed with 113/113 passing tests. Repository validation, CI Cost Guard inspection, Python compile, self-install doctor, full local DEP verification, portable DEP verification, isolated wheel/sdist build, fresh-wheel Hermes install/doctor, and the synthetic Muse pilot also passed.

## Before/after evidence

Before, the released verifier accepted synthetic artifact mutation/deletion, path escape, link traversal, duplicate overwrite, authority downgrade, unsigned L2 approval, and under-bound L3 authorization. After, each case is a deterministic regression test that fails closed while normal signed and routine paths continue.

The authoritative PR workflow now installs the verifier from the exact Base checkout and passes the candidate checkout only as a filesystem/Git argument with candidate-defined Local Green execution disabled. Evidence verification reopens every present artifact and compares exact type, path, size, digest, registration, and redaction association.

## Remaining limitations

- The first PR containing the workflow change is still triggered under the previously trusted Base workflow. It therefore requires fresh independent Review and exact Merge receipt before Merge; subsequent PRs inherit the separated verifier.
- The Muse pilot is synthetic, offline, and disposable. It is not Production readiness and does not authorize real relationship data, images, credentials, deployment, or any L2/L3 operation.
- OS account privilege, branch-rule administrator bypass, owner private-key custody, and Production permissions remain external controls.
