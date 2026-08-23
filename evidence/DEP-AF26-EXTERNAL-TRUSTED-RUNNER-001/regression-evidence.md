# 回歸證據

## Regression test added or strengthened

新增 13 個 Trusted Runner contract tests，涵蓋 exact rehearsal、正式 Schema、peer／
unknown field、binding／payload／capsule drift、bootstrap owner／mode／symlink／hardlink、
unsealed／traversal bundle、approval replay／concurrency、runtime／credential TOCTOU、
socket `SO_PEERCRED`／`SCM_RIGHTS`、canonical profile／source manifest／original managed
bytes 重算、authority snapshot、parent-free secret pipe、timeout／TERM／cleanup 與 CLI surface。

## Related tests executed

- AF26＋repository contract：26 tests。
- 完整 Governance：113 tests。
- Approval concurrent second consumer：20 次重複壓測全綠。
- Ruff、compileall、`sddgov validate`、Wheel build、fresh import／packaged Schema、
  fresh setup／doctor 全綠。
- Agent Factory 0.3 request + 9,925-entry full Hermes bundle 跨 repository rehearsal
  已重算 source／profiles，completed，zero inference。
- Authentication 獨立安全複審 blocking-free，無 Critical／Major／Medium。

## Unaffected paths sampled

Autonomy、Merge Gate、Reviewer、Installer、Evidence、Redaction、CI Guard、Governance 與
Repository Contract 均包含於 113-test full suite；原有 v1.2 Hard Gates 行為未放寬。
