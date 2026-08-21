#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3 is required to render the offline demo result.' >&2
  exit 2
fi

if [[ -f "$repo_root/src/sddgov/cli.py" ]]; then
  if [[ -x "$repo_root/.venv/bin/python" ]]; then
    source_python="$repo_root/.venv/bin/python"
  else
    source_python=$(command -v python3)
  fi
  sddgov_command=(
    env -u PYTHONHOME
    "PYTHONPATH=$repo_root/src"
    "$source_python" -m sddgov.cli
  )
elif [[ -x "$repo_root/.venv/bin/sddgov" ]]; then
  sddgov_command=("$repo_root/.venv/bin/sddgov")
elif command -v sddgov >/dev/null 2>&1; then
  sddgov_command=("$(command -v sddgov)")
else
  printf '%s\n' 'SDG CLI not found. Install the package or create .venv as documented in README.md.' >&2
  exit 2
fi

demo_tmp=$(mktemp -d "${TMPDIR:-/tmp}/sddgov-demo.XXXXXX")
cleanup() {
  case "$demo_tmp" in
    "${TMPDIR:-/tmp}"/sddgov-demo.*) rm -rf -- "$demo_tmp" ;;
  esac
}
on_signal() {
  signal_status=$1
  trap - EXIT INT TERM
  cleanup
  exit "$signal_status"
}
trap cleanup EXIT
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

pilot_status=0
"${sddgov_command[@]}" pilot quick --output "$demo_tmp/result.json" >/dev/null || pilot_status=$?
if [[ ! -s "$demo_tmp/result.json" ]]; then
  printf '%s\n' 'SDG quick pilot failed before producing a result.' >&2
  if (( pilot_status == 0 )); then
    exit 1
  fi
  exit "$pilot_status"
fi

python3 - "$demo_tmp/result.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
checks = (
    ("Routine L1 engineering", "CONTINUE", result["routine_l1_continues"]),
    ("Disguised destructive Production action", "BLOCKED", result["dangerous_downgrade_blocked"]),
    ("Synthetic credential in Evidence", "REDACTED", result["text_redaction_ok"]),
    ("Binary Evidence without reviewed derivative", "BLOCKED", result["binary_evidence_fail_closed"]),
    ("Installed Agent + strict DEP", "VERIFIED", result["agent_install_ok"] and result["strict_dep_ok"]),
)
print("Agentic SDD Governance — offline quick demo")
for label, state, passed in checks:
    print(f"[{'PASS' if passed else 'FAIL'}] {label}: {state}")
print(f"Verdict: {result['verdict']}")
raise SystemExit(0 if result["verdict"] == "PASS" else 1)
PY
