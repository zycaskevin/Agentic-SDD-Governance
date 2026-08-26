# AF26 Synthetic Control Plane Test Double 決策

## 決策

- Decision ID：`AF26-SYNTHETIC-CONTROL-PLANE-L2-001`
- Risk：L2（只變更 rehearsal 證據語意與測試邊界）。
- Owner decision：2026-08-24 明確批准 AF26 僅在 synthetic offline test harness
  使用 control-plane test double。
- Status：approved for this Work Package。

## 精確範圍

- Test double 只存在於 `tests/test_trusted_runner.py` 的合成 fixture。
- Fixture 只使用 ephemeral Ed25519 keys、固定 synthetic secret、`/tmp` 隔離、
  synthetic child、無網路與 `inference_applied=false`。
- 正式 `src/sddgov/trusted_runner.py` 不得加入本地 nonce fallback；仍呼叫正式
  `import_operation_approval`／`evaluate_escalation`，並接受最新 main 的完整
  `operation_payload`、trusted runtime context 與 independent nonce broker contract。
- `mode=production` 繼續 hard-deny，直到 root-owned runtime context／nonce broker、
  dedicated UID、cgroup v2 descendant containment 與 FD-bound runtime chain 完成。

## 不得宣稱

- Synthetic double 不是 Owner-signed L3 receipt、root-owned control plane 或真實 broker。
- 測試通過只證明 AF26 對正式 control-plane API 的 request／ordering／fail-closed contract，
  不證明真實 L3 全鏈路、Live、Production、Promotion、部署或發布完成。

## 驗證與反向守門

- Positive：test double 可讓純合成 rehearsal 驗證 approval → secret → child → cleanup。
- Negative：移除 double 後必須在 approval 前 fail closed，且 secret 不開啟、runtime 不啟動。
- Schema：approval receipt 與 consume request 必須攜帶相同 exact operation payload。
- Regression：Trusted Runner targeted、repository contracts、portable strict DEP、full Local
  Green、fresh Wheel／doctor 與獨立安全審查全綠。

## 重新開啟條件

若 test double 進入正式 source、能被 CLI／runtime 啟用、能替代 root-owned broker、測試使用
非合成 credential／網路／推論，或文件把它宣稱為真實 L3，立即停止並重新取得 L2/L3 決策。

## 權限界線

本文件記錄本次程式與測試語意決策，不是可匯入 autonomy control plane 的 Ed25519 L2/L3
receipt，也不得授權任何真實 operation。
