# 重現

## Expected

AF26 在最新 `origin/main` 上應通過 Trusted Runner targeted tests、repository contracts、
所有 tracked Proof DEP 的 portable strict verification，以及完整 Local Green。

## Actual

`env PYTHONPATH=src python3 -m unittest -v tests.test_trusted_runner
tests.test_repository_contract` 執行 32 tests，有 9 failures；完整 Local Gate 執行
250 tests 亦有 9 failures並退出 1。

## Deterministic steps

1. 從 `cb65de5...` 合併 `origin/main@92f4ba8...`，產生 `6534fce...`。
2. 執行 `.venv/bin/sddgov ci verify .`，contract 驗證通過。
3. 執行 `.venv/bin/sddgov ci local-gate .`。
4. 以 targeted command 重現相同 approval／manifest／DEP failures。

## Environment and preconditions

Branch `codex/af26-trusted-runner`，Linux aarch64，system Python 3.12.3，
`PYTHONPATH=src`；只有合成資料，沒有真實 credential、網路或推論。
