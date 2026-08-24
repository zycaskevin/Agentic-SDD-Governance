# Rollback

rollback_version: 3.0
target: AF26 append-only atomic rollback normalization reapply
rollback_action: git_revert
rollback_ref: 8a8d43405701101a443512c7444b8ff44c0bfa93
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

若 atomic ref不能在 exact reviewed head乾淨 revert、revert後 non-Evidence／non-audit tree不等於
trusted Base、或 normalization後 final tree不再等於 SHA-256固定的原始 patch，立即維持 Merge blocked。

## Reversible steps

在 reviewed Git workflow中 revert `8a8d43405701101a443512c7444b8ff44c0bfa93`；該 inverse
只把 Evidence／audit以外的 AF26 final tree恢復成 trusted Base。接著從 reverted source執行
`setup-agent --force`，不得手動刪除 Evidence或修改受信 Reviewer資料。

## Data compatibility

沒有資料庫、正式資料、credential、nonce或已發布 Schema migration。Rollback會移除尚未發布的
AF26 source／Schema／tests／docs surface；所有依賴 AF26 exact change digest的 receipt與Proof失效。

## Post-rollback verification

從 reverted source重新執行 setup-agent、Doctor、`unittest`完整 module、repository validation、
CI Local Gate及受影響 DEP strict verification；確認 non-Evidence／non-audit tree等於 exact Base，
且 AF26 trusted-runner CLI不再存在後，才可接受 rollback結果。
