# Regression Evidence

## Regression test added or strengthened

新增 history-level executable check：

- trusted Base 到 final non-Evidence／non-audit tree 的 binary patch在 normalization前後
  SHA-256 均為 `90eca65831b8f1fbc57429a71b9fbf605344a1767e39d6d2d45ab706f595cfde`，
  且 `cmp` 逐位元相等；
- `_rollback_ref_is_cleanly_revertible()` 對 atomic ref
  `8a8d43405701101a443512c7444b8ff44c0bfa93`、exact Base與該 reviewed head回傳 `True`。
- `_rollback_contract()` 對最終 `rollback.md` 回傳 version `3.0` 與相同 immutable ref，
  所有說明段落均為 comment，不會被當成可執行欄位。

## Related tests executed

原始 fail-closed `merge verify --skip-local-checks` 已由 clean detached Red 重現；四份既有 AF26
DEP portable strict通過。Normalization後 `ci verify`通過，完整 Local Gate執行256項測試全綠，
repository validate通過。新增 DEP strict與 exact gate preflight於 audit metadata固定後再驗。

## Unaffected paths sampled

Normalization patch明確排除 `evidence/**` 與 `.sddgov/**`；不接觸 reviewer trust、私鑰、
GitHub remote、credential、Runner execution、network、inference、Production與部署。重放 patch
涵蓋 25 個既有 AF26 non-Evidence檔案，沒有新增產品差異。
