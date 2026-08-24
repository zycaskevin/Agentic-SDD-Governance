# 驗證

## Green command and result

- `env PYTHONPATH=src python3 -m unittest -q tests.test_trusted_runner
  tests.test_repository_contract`：33 tests，通過。
- `.venv/bin/sddgov ci local-gate .`：251 tests，通過；兩個 contract commands
  return code 0，repository validation 通過。
- `DEP-AF26-EXTERNAL-TRUSTED-RUNNER-001` 與
  `DEP-AF26-PR-LOCAL-GATE-001`：portable strict verify 通過。
- Ruff 0.14.10 scoped、system Python compileall、`git diff --check`：通過。
- fresh Wheel dev9：只從唯一 `/tmp` target import；launcher 與 request schema 均來自
  Wheel；fresh setup-agent／doctor 為 69 managed files、0 error、0 warning。
- 獨立安全審查：read-only static final pass 無 Critical／Major／Medium blocker；確認 exact
  payload、test-only doubles、no-double fail-close、production bootstrap hard-deny，以及
  canonical／packaged／installed schema 同步。此審查未重跑測試，執行結果以上述 Green 為準。

## Before/after evidence

Before：targeted 32 tests／full 250 tests 均有 9 failures。After：相同範圍擴充 no-fallback
guard 後為 targeted 33／full 251 tests 全綠；正式 source 仍無 control-plane fallback。

## Remaining limitations

Production 仍需不同 UID、cgroup v2 descendant containment、FD-bound runtime execution
chain、固定 `/etc` runtime context 與 root-owned nonce broker；本 Work Package 不啟用它們。
