# Verification

## Green command and result

`cmp` normalization前後 binary patch：exit 0；兩份 SHA-256皆為
`90eca65831b8f1fbc57429a71b9fbf605344a1767e39d6d2d45ab706f595cfde`。
以 exact Base／atomic ref執行 `_rollback_ref_is_cleanly_revertible()`：`True`。
以 immutable `rollback.md` bytes執行 `_rollback_contract()`：回傳有效 v3 contract。

## Before/after evidence

Before：clean `9b38261` audit head 的 Merge verifier在 receipt前以
`rollback record is missing or incomplete`、exit 3拒絕。

After：single atomic ref `8a8d434057...` 可乾淨 revert，且其 final AF26 tree與修正前逐位元一致。
同一 final tree 的 CI contract verification通過；Local Gate執行256項測試全綠，並通過
repository validation。五份 raw輸出均經 deterministic redaction，兩個 home path已遮蔽。

## Remaining limitations

外部獨立 signer identity／private key仍不可由 Builder環境取得；本 DEP不產生 receipt，
不授權 push或 hosted CI。Exact audit gate完成後，merge preflight應只在 fresh receipt缺失處
fail closed；該預期停止點不等於 receipt、Merge、Production或部署完成。
