# v0.2.0-experimental.9 Release Notes

## Outcome

This patch release preserves the experimental.8 Security and Autonomy hard
gates while fixing an over-restrictive CI Cost Guard boundary. An opt-in
self-hosted job may now use a strictly narrower flat conjunction only when it
independently binds the matching PR event family and requires a non-Draft PR.
Legacy cross-event guards remain compatible; disjunctions, parentheses,
functions, nested interpolation, incomplete comparisons, and mismatched event
or Draft atoms remain fail-closed.

## Install

Download the wheel and `SHA256SUMS.txt`, then let the machine verify the exact wheel before installation:

```bash
set -eu
mkdir -p sdg-release
gh release download v0.2.0-experimental.9 \
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
test "$(.venv-sddgov/bin/sddgov --version)" = "0.2.0-experimental.9"
```

Install the same verified package into Codex or Hermes:

```bash
.venv-sddgov/bin/sddgov setup-agent /path/to/project --agent codex --profile team-standard
.venv-sddgov/bin/sddgov doctor /path/to/project

.venv-sddgov/bin/sddgov setup-agent /path/to/hermes-project --agent hermes --profile team-standard
.venv-sddgov/bin/sddgov doctor /path/to/hermes-project
```

## Verified release boundaries

- Cost Guard targeted suite: 22 tests passed, including legacy positive paths,
  strict PR and `pull_request_target` conjunctions, and fail-closed hostile cases.
- Repository suite: 232 tests passed in the normal matrix; the sandbox-only
  AF_UNIX positive path passed separately on the normal host boundary.
- `sddgov validate`, `sddgov ci verify`, Local Green, and Doctor passed.
- Two builds from the same immutable source and `SOURCE_DATE_EPOCH` produced a
  byte-identical wheel.
- A fresh isolated wheel installation returned
  `0.2.0-experimental.9` and changed the verified stricter fail-closed
  conjunction from Cost Guard rejection to PASS.
- Independent protected-file review, exact Merge Gate, one hosted trusted
  verifier run, and artifact publication remain mandatory release gates; these
  notes do not substitute for their receipts.

The Release includes machine-generated `SHA256SUMS.txt` and an independently signed `RELEASE_PROVENANCE.json` that binds the exact merged commit and downloadable artifacts.

## Important limits

- This remains an experimental pre-release, not a stable or compliance-certified framework.
- The Local Redaction Gateway is a conservative security boundary, not a legal anonymization certification.
- Binary evidence remains fail-closed until an approved redacted derivative exists.
- Benchmark fixtures validate the harness; they do not prove debugging superiority.
- The package is distributed through GitHub Release, not PyPI.
- Production credentials, payments, destructive data operations, new external access, and subjective UAT remain outside routine L0/L1 authorization.
