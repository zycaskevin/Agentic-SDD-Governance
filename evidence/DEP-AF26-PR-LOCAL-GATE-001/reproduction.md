# 重現

## Expected

`.sddgov/ci-cost-guard.json` 指定的 `python3` source-checkout 全套測試應全綠，
不需先將當前 Wheel 安裝進系統 Python。

## Actual

Local Gate 執行 113 tests 時有 5 個 rehearsal child tests 變成
`stopped_fail_closed`／`child_failed`；相同 suite 以 editable `.venv` Python 執行會通過。

## Deterministic steps

1. 在 repository root 執行 `.venv/bin/sddgov ci verify .`。
2. 執行 `.venv/bin/sddgov ci local-gate .`。
3. 觀察契約命令 `python3 -m unittest discover -s tests -v` 退出 1，五個
   Trusted Runner child-path tests 失敗。

## Environment and preconditions

Commit `232be566...`，branch `codex/af26-trusted-runner`，Linux aarch64，
system Python 3.12.3，`PYTHONPATH=src`；只有合成資料且無網路。
