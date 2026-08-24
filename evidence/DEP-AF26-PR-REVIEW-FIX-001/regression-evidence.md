# 回歸證據

## 新增或強化的回歸測試

- `test_child_setup_failures_close_every_owned_descriptor`：stderr open、secret pipe write、
  Popen三個 fault injection後，所有 captured FD均必須 EBADF。
- `test_descriptor_close_failure_is_reported_fail_closed`：模擬 parent close失敗時 signed result
  必須為 `descriptor_cleanup_failed`且 `descriptors_closed=false`。
- `test_unexpected_failure_emits_schema_safe_reason`：未預期例外只回傳固定安全 token並通過 schema。
- published schema test加入 124000 ms observation；120秒 execution deadline不再被誤當 observation max。
- setup failure test確認 patch與 temp root透過 `addCleanup()`還原。
- redaction test確認 `/home`／`/Users`路徑與行尾空白被 deterministic移除。

## 相關測試

- Trusted Runner＋redaction＋repository contracts：45 tests，通過。
- 完整 Local Gate：256 tests，通過；repository validate與 CI contract verify通過。
- Ruff 0.14.10、compileall（`/tmp` pycache）、`git diff --check`：通過。
- 兩個受影響的既有 AF26 DEP在新 redaction規則重建後 portable strict verify通過。
- Fresh dev9 Wheel：唯一 `/tmp` target import、packaged schema／rules parity、69-file
  setup-agent／doctor通過，0 error／0 warning。

## 未受影響路徑取樣

Full Local Gate取樣 autonomy、Evidence、Merge Gate、Installer、Reviewer、CI Guard與既有
Trusted Runner exact approval/no-fallback/production hard-deny。未執行真實 credential、網路、
Provider inference、Production、Promotion、Gate Enforce、release或deployment。
