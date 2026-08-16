# v0.2.0-experimental.8 Release Notes

## Outcome

This release completes the experimental.8 Security and Autonomy hardening cycle without turning routine engineering into a human approval workflow.

L0/L1 Issue, Branch, implementation, test, Commit, Push, PR, Review, review-fix, CI, Merge, retry, and checksum work remains autonomous. Checkpoints remain informational. Machine-verifiable uncertainty must be resolved through repository evidence, tests, CI, or tools; it cannot be promoted into an owner prompt. A genuine L2 product decision, concrete L3 operation, Operational Action, or subjective Necessary UAT remains fail-closed and bounded.

The release also closes the verifier, Evidence, filesystem, Rollback, authority-envelope, decision-memory, and first-consumer bootstrap gaps found during the experimental.7 hostile review. The final Security and Autonomy reviews reported P0=0/P1=0 before publication.

## Install

Download the wheel and `SHA256SUMS.txt`, then let the machine verify the exact wheel before installation:

```bash
set -eu
mkdir -p sdg-release
gh release download v0.2.0-experimental.8 \
  --repo zycaskevin/Agentic-SDD-Governance \
  --pattern '*.whl' \
  --pattern 'SHA256SUMS.txt' \
  --dir sdg-release

wheel_count=$(find sdg-release -maxdepth 1 -type f -name '*.whl' | wc -l | tr -d ' ')
test "$wheel_count" -eq 1
wheel_name=$(find sdg-release -maxdepth 1 -type f -name '*.whl' -print -quit)
test -n "$wheel_name"
case "$wheel_name" in *-py3-none-any.whl) ;; *) exit 1 ;; esac
wheel_base=$(basename "$wheel_name")
checksum_count=$(awk -v name="$wheel_base" '$2 == name { count += 1 } END { print count + 0 }' sdg-release/SHA256SUMS.txt)
test "$checksum_count" -eq 1
awk -v name="$wheel_base" '$2 == name { print }' \
  sdg-release/SHA256SUMS.txt > sdg-release/wheel.SHA256SUMS
if command -v sha256sum >/dev/null 2>&1; then
  (cd sdg-release && sha256sum --check --strict wheel.SHA256SUMS)
else
  (cd sdg-release && shasum -a 256 --check --strict wheel.SHA256SUMS)
fi
python3 -m venv .venv-sddgov
.venv-sddgov/bin/python -m pip install "$wheel_name"
test "$(.venv-sddgov/bin/sddgov --version)" = "0.2.0-experimental.8"
```

Install the same verified package into Codex or Hermes:

```bash
.venv-sddgov/bin/sddgov setup-agent /path/to/project --agent codex --profile team-standard
.venv-sddgov/bin/sddgov doctor /path/to/project

.venv-sddgov/bin/sddgov setup-agent /path/to/hermes-project --agent hermes --profile team-standard
.venv-sddgov/bin/sddgov doctor /path/to/hermes-project
```

## Verified release boundaries

- Final Security review: P0=0, P1=0.
- Final Autonomy and approval-budget review: P0=0, P1=0.
- Repository suite: 229 tests with no failures; the sandbox-only AF_UNIX positive path was independently verified outside the restricted sandbox.
- Python 3.10 and Python 3.12 consumer/verifier paths: passed.
- `sddgov validate`, `sddgov ci verify`, Local Green, Doctor, and exact Merge Gate: passed.
- All tracked Proof DEPs: current portable strict verification passed.
- Rollback drill restored the trusted Base runtime and passed Doctor plus its declared test module.
- Wheel, sdist, ZIP, and Git bundle safety checks: passed.
- Fresh-wheel Codex/Hermes installation and offline synthetic Muse pilot: passed with no real data or network use.
- GitHub-hosted trusted verifier: passed once on the frozen exact PR Head.
- Branch protection requires the machine `verify` check and does not require a human Reviewer count.

The Release includes machine-generated `SHA256SUMS.txt` and an independently signed `RELEASE_PROVENANCE.json` that binds the exact merged commit and downloadable artifacts.

## Important limits

- This remains an experimental pre-release, not a stable or compliance-certified framework.
- The Local Redaction Gateway is a conservative security boundary, not a legal anonymization certification.
- Binary evidence remains fail-closed until an approved redacted derivative exists.
- Benchmark fixtures validate the harness; they do not prove debugging superiority.
- The package is distributed through GitHub Release, not PyPI.
- Production credentials, payments, destructive data operations, new external access, and subjective UAT remain outside routine L0/L1 authorization.
