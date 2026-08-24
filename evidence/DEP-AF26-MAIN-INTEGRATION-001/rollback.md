# Rollback

rollback_version: 3.0
target: AF26 latest-main approval and portable-proof integration fix
rollback_action: git_revert
rollback_ref: e27eb8ef99908c8143f6cef706a25f8b569fddfa
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

若 exact payload 遷移降低 main 的 L3 control-plane條件、使 production 不再 hard-deny，
或造成 AF26 以外治理測試回歸，執行 bounded rollback。

## Reversible steps

在 reviewed Git workflow 中 revert 最終 AF26 integration fix commit；不得回滾最新 main。

## Data compatibility

沒有 production data、資料庫或真實 nonce；approval request schema 回復前一版時，未發布的
Agent Factory rehearsal fixture必須同步回復。

## Post-rollback verification

從 revert 後 source 重新執行 `setup-agent --force`，再執行 doctor、Trusted Runner／
repository contract modules與完整 Local Green；若舊契約仍與 main 不相容，維持 PR blocked。
