# 根因假說

## Hypothesis

`TrustedRunner._run_child()` 使用 `sys.executable -I -m sddgov._trusted_exec`。`-I`
正確地隔離 caller 的 `PYTHONPATH`，但也使尚未安裝的 source checkout 無法載入
launcher module。

## Supporting evidence

- 失敗只出現於需要 child launcher 的五個 tests。
- 同一 tests 以已 editable-install package 的 `.venv` Python 執行會通過。
- child stderr hash 路徑 fail closed，沒有 credential 或 output 洩漏。

## Contradicting evidence

Approval、sealed bundle、profile／source 與無 child 的失敗關閉測試均通過，表示不是
request contract、approval ordering 或 bundle verifier 回歸。

## Falsification test

將 launcher 改為同 package 目錄的絕對 script path，仍保留 `-I`；若系統
Python source checkout 的 targeted 與 Local Green Gate 全綠，且 Wheel fresh install 仍通過，
則根因確認。

## Conclusion

根因已確認：module-mode launcher 對「未安裝 source checkout + isolated mode」有
隱含 packaging 依賴。
