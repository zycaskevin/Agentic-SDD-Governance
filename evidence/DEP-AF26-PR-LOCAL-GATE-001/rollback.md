# 回滾

## Trigger

絕對 launcher script path 無法在 source checkout 或 Wheel 內執行，或改變 secret-after-approval、
cleanup、signed result 與 production hard-deny 任一契約。

## Reversible steps

只回滾 `_run_child()` launcher argv 與相關 test assertion，恢復 module-mode 呼叫；
保留 AF26 其餘 contract，但立即將所有綁定被回滾 launcher／change digest 的 Proof 標示失效，
不得沿用為 merge evidence。修正後必須重新收集 Red／Green、重算 manifest／redaction metadata，
並重新執行 strict verification及獨立 review。

## Data compatibility

無資料庫、Schema、wire data 或正式狀態變更。

## Post-rollback verification

重跑 Trusted Runner targeted tests／Local Gate與所有受影響 DEP portable strict verification；
只有新 Proof 綁定 revert後 exact head且獨立 review通過，才能解除 Push blocked。若 module mode
仍無法通過 system Python，維持 blocked。
