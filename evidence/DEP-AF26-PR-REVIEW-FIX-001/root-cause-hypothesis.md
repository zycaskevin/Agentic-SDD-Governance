# 根因假設

## 假設

`_run_child()` 的 descriptor ownership 分成多個相鄰 try/finally，早期 open／pipe／write
例外可在完整 cleanup scope 建立前離開；`execute()` 又以 `descriptors_closed=true` 起始，
未取得 child cleanup 狀態。Result reason 與 duration schema 分別把 Python exception 類型及
120 秒 execution budget 誤當成安全公開 token與完整 wall-clock observation 上限。舊 rollback
與 redaction inventory 也沒有把 Proof invalidation、home path及 trailing whitespace納入契約。

## 支持證據

- stderr open 與 secret pipe write 注入失敗後，`os.fstat()` 仍可讀到 parent-owned FD。
- 三個 child setup failure 均回傳 `unexpected_error:OSError`，不符合 reason pattern。
- `duration_ms=124000` 只因 Schema maximum 120000 被拒絕。
- setup 中途失敗後，inner runtime context patch仍覆蓋 outer fixture。
- `git diff --check` 與 `/home/` inventory精確定位 shareable artifact。

## 反證

Popen failure 已由既有內層 finally關閉當時已建立的 FD；因此不是所有 child failure都洩漏。
正式 source 的 environment 已由 parent allowlist建構，CodeRabbit 的 ambient credential finding
不成立；credential `lstat` 也已轉成 `TrustedRunnerViolation`。

## 可證偽測試

以 stderr open、secret pipe write與 Popen 三個 fault injection測試逐一確認所有 captured FD
均為 EBADF；以 generic RuntimeError確認 signed reason固定且 schema-valid；以 124000 ms
observation確認 schema接受；故障 setUp後執行 cleanups必須還原所有 patch與刪除 temp root。

## 結論

根因已確認。修復不得改動 approval、secret ordering、production hard-deny或正式 control-plane
contract，只統一 parent FD ownership／結果語意，並修正 deterministic redaction與舊 Proof truth。
