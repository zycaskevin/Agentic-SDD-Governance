# 重現

## 預期

所有 Runner-owned FD 在任何 child setup／launch 結果都必須關閉，且 signed result 的
`descriptors_closed`、`reason` 與 `duration_ms` 必須符合實際狀態及公開 Schema。Rollback
不得保留綁定已回滾 launcher 的有效 Proof；shareable evidence 不得暴露本機 home path。

## 實際

pipe write／第二個 stdio open 的早期例外發生在完整 cleanup scope 外；top-level unexpected
reason 含冒號與類別名稱；Schema 把 duration 固定為 120000 ms；launcher rollback 宣稱保留
舊 Proof；`git diff --check origin/main...HEAD` 指向 shareable Red log trailing whitespace，
同一 artifact 含 `/home/zycas/...`。

## 決定性步驟

1. 執行新增的 early pipe／stdio failure tests，確認 PR head 留下受控 FD。
2. 執行 unexpected failure／extended timeout result schema tests，確認公開 Schema 拒絕結果。
3. 執行 `git diff --check origin/main...HEAD`，確認 shareable artifact 格式失敗。
4. 以 `rg` 檢查 shareable artifacts 的 `/home/<user>/` 路徑。

## 環境與前置條件

PR #53 exact base `92f4ba8388ecf1ef1f3407db6c49cef62f6ee196`、head
`2f9107b50a79aca4389f84ffa55706fccce46f26`；無真實 credential、網路、Provider inference、
Promotion、Gate Enforce 或 deployment。
