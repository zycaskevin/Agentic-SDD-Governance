# 回歸證據

## Regression test added or strengthened

新增 exact approval operation payload 的 code／schema／test binding；新增
`test_rehearsal_has_no_control_plane_fallback`，以正式 loader 與 unavailable broker 驗證
沒有 synthetic double 時在 approval 前 fail closed，secret 不開啟、runtime 不啟動；
既有 production hard-deny 不變。

## Related tests executed

- 原始 targeted integration：33 tests，通過。
- full Local Gate：251 tests，通過；repository validation 通過。
- 兩個既有 AF26 Proof DEP portable strict verification：通過。
- Ruff 0.14.10 scoped check、compileall、`git diff --check`：通過。
- fresh Wheel `agentic_sdd_governance-0.2.0.dev9-py3-none-any.whl`：isolated import、
  co-located launcher、packaged schema、69-file setup-agent／doctor 通過；0 error／warning。
- 獨立 read-only security final pass：無 Critical／Major／Medium blocker；未重跑測試。

## Unaffected paths sampled

Autonomy、Merge Gate、Evidence、Installer、CI Guard、Reviewer、Redaction 與 schema paths
由 full Local Gate 取樣；Agent Factory 跨 repo rehearsal另列為後續相容性驗證，且不得
宣稱真實 L3 control plane。
