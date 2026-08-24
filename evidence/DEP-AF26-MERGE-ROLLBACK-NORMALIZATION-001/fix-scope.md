# Fix Scope

## Smallest sufficient change

保留公開 branch 的既有歷史，不 force-push；新增一組 append-only normalization commits：
第一筆只把 Evidence／`.sddgov` 以外的候選 tree還原成 exact trusted Base，第二筆以單一 atomic
commit重放完全相同的 AF26 final tree。將第二筆 SHA 綁入本 DEP rollback contract，再以
Evidence-only commit封存 Proof，最後重新建立 exact audit gate。

## Files or components in scope

- Git commit history（append-only baseline／atomic reapply）。
- `work-packages/WP-AF26-EXTERNAL-TRUSTED-RUNNER-001.md` 的 Evidence／狀態記錄。
- `evidence/DEP-AF26-MERGE-ROLLBACK-NORMALIZATION-001/`。
- 後續 audit-only `.sddgov/merge-gate.json`；公開 receipt仍由外部獨立 Reviewer產生。

## Explicit non-scope

不改變 AF26 final source／Schema／tests／CLI／文件語意；不 force-push、不改 Base、不建立或
bootstrap reviewer、不接觸私鑰、不修改 GitHub trust variable、不推送、不執行 hosted CI、
Merge、Release、Production、Promotion、Gate Enforce或部署。

## Blast radius

最終 repository tree的非 Evidence／audit內容應與 normalization前逐位元一致。新增影響只限
可見 Git history、L1 DEP與 exact gate metadata；若 tree digest不同或 rollback predicate仍失敗，
立即停止且不交付 Reviewer。
