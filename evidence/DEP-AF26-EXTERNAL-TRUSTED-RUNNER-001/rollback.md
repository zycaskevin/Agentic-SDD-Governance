# 回滾

## Trigger

Runner 接受同 UID／root production、未 sealed FD、material drift、approval replay、
secret-before-approval、caller path／argv／env、或 cleanup／zeroize 不完整時立即回滾。

## Reversible steps

移除 `trusted_runner.py`、`_trusted_exec.py`、CLI surface、三份 Schema／packaged copies、
tests／SDD／Work Package／DEP；回復 CHANGELOG／Roadmap。保留 v1.2 Hard Gates 與 AF25
offline-only capsule。

## Data compatibility

無資料庫、正式資料或 credential format migration；AF26 尚未發布或配置 production
service，回滾只影響本機未發布 API／resources。

## Post-rollback verification

重跑 100 個既有 Governance tests（排除 AF26 11 項）、`sddgov validate`、Wheel import；
確認 `sddgov trusted-runner` 不再出現且 Autonomy／Merge Gate 不變。
