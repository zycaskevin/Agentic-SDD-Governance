# 回滾

## Trigger

絕對 launcher script path 無法在 source checkout 或 Wheel 內執行，或改變 secret-after-approval、
cleanup、signed result 與 production hard-deny 任一契約。

## Reversible steps

只回滾 `_run_child()` launcher argv 與相關 test assertion，恢復 module-mode 呼叫；
保留 AF26 其餘 contract 與 Proof。

## Data compatibility

無資料庫、Schema、wire data 或正式狀態變更。

## Post-rollback verification

重跑 Trusted Runner targeted tests／Local Gate；若 module mode 仍無法通過 system Python，
維持 Push blocked。
