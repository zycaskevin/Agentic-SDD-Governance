# Verification

## Green command and result

`PYTHONPATH=src python -m pytest -q` completed with 132/132 tests passing on macOS outside the restricted sandbox after three independent Review rounds were converted to adversarial cases. The third round caught that executing a verified `/dev/fd` Broker descriptor fails on macOS; the replacement now uses a real Unix socket protocol at fixed root-controlled platform paths, and its positive test exercised a real AF_UNIX connection. Repository validation, CI Cost Guard inspection/local gate, Python compile, full local and portable DEP verification, hash-locked dependency installation, and the offline synthetic Muse pilot passed before sealing the implementation commit. Exact-Head wheel/sdist and fresh-wheel Hermes install/doctor remain subject to one final run after that commit is sealed.

## Before/after evidence

Before, the released/candidate verifier accepted synthetic artifact mutation/deletion, omitted raw rows, extension/HAR disguise, path escape or parent-replacement side effects, link traversal, duplicate overwrite, caller-created Owner roots, caller-asserted L2 freshness, unbound L3 Runtime Context, cross-clone replay, and invalid Reviewer bootstrap fallback. After, each case is a deterministic regression test that fails closed while normal L0/L1 paths continue.

The authoritative PR workflow now installs the verifier from the exact Base checkout and passes the candidate checkout only as a filesystem/Git argument with candidate-defined Local Green execution disabled. Evidence verification reopens every present artifact and compares exact type, path, size, digest, registration, and redaction association.

## Remaining limitations

- The first PR containing the workflow change is still triggered under the previously trusted Base workflow. It therefore requires fresh independent Review and exact Merge receipt before Merge; subsequent PRs inherit the separated verifier.
- The Muse pilot is synthetic, offline, and disposable. It is not Production readiness and does not authorize real relationship data, images, credentials, deployment, or any L2/L3 operation.
- L3 `CONTINUE` requires a non-root Agent plus separately deployed root-owned Runtime Context and Unix nonce Broker. The Broker path is fixed to `/private/var/db/sddgov/approval-broker.sock` on macOS and `/run/sddgov/approval-broker.sock` on Linux; without it SDG returns machine-actionable `BLOCKED`. This repository does not claim a clone-local file provides environment identity or global single use.
- Portable verification proves committed metadata consistency and shareable bytes, not the existence or honesty of omitted raw bytes.
- OS account privilege, branch-rule administrator bypass, owner private-key custody, and Production permissions remain external controls.
