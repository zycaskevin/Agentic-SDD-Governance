# 根因假說

## Hypothesis

AF26 建立於舊版 autonomy／evidence／installer contract。最新 main 要求 L3 approval
receipt 與 consume request 皆攜帶相同 exact `operation_payload`，且 consume 必須通過
trusted runtime context 與 independent nonce broker；AF26 receipt 與 decision request
仍是 legacy shape。新版 portable DEP metadata 另新增 media／size provenance，installed
governance manifest 也尚未納入 AF26 三個 schema。

## Supporting evidence

- 七個 Trusted Runner failures 均在 approval 前或 approval consume 處 fail closed，
  典型 reason 為 `approval_verification_failed`。
- `autonomy.import_operation_approval()` 現在強制 `operation_payload` 與 runtime context；
  `evaluate_escalation()` 也要求同一 payload並透過 broker consume nonce。
- repository doctor 精確列出三個 omitted Trusted Runner schemas。
- 兩個 AF26 Proof DEP 的 strict verifier 精確指出舊 manifest／redaction report 缺少
  新版 provenance 欄位。

## Contradicting evidence

Bundle、profile/source material、production hard-deny、request policy 與 no-child attack
tests 仍通過；表示不是 sealed bundle、containment 或 launcher 回歸。

## Falsification test

加入由 AF26 operation 決定性產生的 exact approval payload，讓 receipt 與 consume request
完全相同；測試只以 synthetic control-plane stub 驗證 rehearsal，實作不提供 broker fallback。
同步 refresh installed governance 與遷移兩個舊 DEP provenance。若 targeted、portable strict
與完整 Local Green 全綠，根因成立。

## Conclusion

根因已確認為 AF26 與最新 main 的三處契約漂移，而非放寬 production authority 可以解決。
