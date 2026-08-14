# v0.2.0-experimental.6 Release Notes

## Outcome

This release completes the SDG Autonomous Development v1.2 hard-gate implementation while preserving autonomy for routine L0/L1 engineering.

Agents now default to `CONTINUE` for machine-verifiable work, reuse recorded decisions, keep Checkpoints informational, and emit strict `ACTION REQUIRED` packages only for unresolved L2, concrete L3, Operational Action, or Necessary UAT boundaries. SHA-256 remains invisible machine-to-machine integrity infrastructure and is never a human approval token.

The release also makes the remaining trust boundaries executable: canonical action classification prevents dangerous authority downgrades, L3 uses trusted Ed25519 receipts with exact binding and atomic single-use consumption, and `sddgov merge verify` enforces Local Green, strict DEP, Redaction, Rollback, raw-evidence exclusion, and independent protected-file Review.

## Install

Download the wheel and `SHA256SUMS.txt` from the GitHub Release, then let the machine verify the wheel before installation:

```bash
set -eu
mkdir -p sdg-release
gh release download v0.2.0-experimental.6 \
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
installed_version=$(.venv-sddgov/bin/sddgov --version)
test "$installed_version" = "0.2.0-experimental.6"
```

Install into a Codex or Hermes project:

```bash
.venv-sddgov/bin/sddgov setup-agent /path/to/project --agent codex --profile team-standard
.venv-sddgov/bin/sddgov doctor /path/to/project

# Hermes uses the same package and governance core.
.venv-sddgov/bin/sddgov setup-agent /path/to/project --agent hermes --profile team-standard
```

## Verification performed

- Complete repository suite: 100 tests passed.
- `sddgov validate`, `sddgov doctor`, and `sddgov ci verify`: passed.
- Strict verification for both v1.2 Debug Evidence Packages: passed.
- Exact Merge Gate, independent Ed25519 Review Receipt, pull-request Governance, and post-Merge `main` Governance: passed.
- PEP 517 wheel and sdist build plus isolated wheel installation: passed.
- Clean Codex and Hermes setup plus `doctor`: passed.
- ZIP, Git bundle, wheel, and sdist machine-generated SHA-256 verification: passed.

## Important limits

- This remains an experimental pre-release, not a stable or compliance-certified framework.
- The Local Redaction Gateway is a conservative MVP, not a legal anonymization certification.
- Binary evidence remains fail-closed until an approved redacted derivative exists.
- Benchmark fixtures validate the harness; they do not prove debugging superiority.
- Hermes installation and the independent Reviewer path are verified; each distinct Hermes host should still run a fresh behavior pilot.
- The package is distributed through GitHub Release, not PyPI. Private repositories require an authenticated GitHub account with access.
- This release does not change GitHub Billing, repository visibility, Production infrastructure, credentials, or deployment state.
