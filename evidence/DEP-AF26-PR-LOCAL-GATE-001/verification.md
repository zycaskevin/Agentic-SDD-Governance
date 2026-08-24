# 驗證

## Green command and result

- system Python source checkout：`env PYTHONPATH=src python3 -m unittest -q
  tests.test_trusted_runner`，13 tests，通過。
- editable venv：`.venv/bin/python -m unittest -q tests.test_trusted_runner`，
  13 tests，通過。
- Local Green：`.venv/bin/sddgov ci local-gate .`，113 tests 通過；兩個契約命令
  return code 均為 0；`sddgov validate .` 通過。
- 靜態檢查：scoped Ruff、system Python compileall 與 `git diff --check` 均通過。
- Fresh Wheel：build `agentic_sdd_governance-0.2.0.dev6-py3-none-any.whl`，安裝至
  唯一 `/tmp` target；import origin 與 co-located `_trusted_exec.py` 均位於該 target；
  `setup-agent --profile team-standard` 與 `doctor` 通過，62 managed files，0 error，
  0 warning。
- 獨立安全審查：無 Critical／Major／Medium blocker；確認絕對 launcher、FD index、
  secret 不進 parent env，且 production hard-deny 未放寬。

## Before/after evidence

Before：system Python source checkout 的五個 child tests 失敗。After：相同 Local
Gate 全套 113 tests 與 fresh Wheel doctor 均通過；rehearsal launcher 不再依賴
source checkout 已安裝。

## Remaining limitations

Production 仍需 cgroup v2 descendant containment 與 FD-bound runtime chain，不在本修正範圍。
