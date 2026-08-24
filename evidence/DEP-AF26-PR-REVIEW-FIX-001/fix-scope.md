# 修復範圍

## 最小充分變更

以單一 `_run_child()` ownership scope管理 stdout／stderr／secret pipe四個 FD；任何例外後逐一
關閉仍持有的 descriptor，使用固定 schema-safe unexpected reason，並讓 observation schema
表達 timeout後 termination期間。測試 fixture每取得一項資源即註冊 cleanup。更正 launcher
rollback的 Proof invalidation，並以 deterministic home-path／trailing-whitespace redaction重建
受影響 AF26 shareable artifacts與 metadata。

## 範圍內檔案／元件

- `src/sddgov/trusted_runner.py` 與 Trusted Runner canonical／packaged／installed result schema。
- `tests/test_trusted_runner.py`、`tests/test_redaction.py`及 repository contract parity。
- `src/sddgov/redaction.py`、canonical／packaged／installed redaction inventory。
- 受影響 AF26 DEP、Work Package／SDD狀態與本次 review-fix DEP。

## 明確非範圍

不新增 nonce/control-plane fallback，不配置 root-owned context／broker／service account／cgroup v2／
FD-bound production runtime，不讀 credential，不執行 Hermes／network／inference／Production／
Promotion／Gate Enforce／release／deploy，也不簽署 protected review receipt或重跑 hosted CI。

## 影響面

Runner rehearsal failure與結果 envelope、所有文字 DEP redaction，以及兩個既有 AF26 Proof artifact。
完整 Governance Local Gate、fresh setup-agent／doctor與三份 schema／inventory parity必須重驗。
