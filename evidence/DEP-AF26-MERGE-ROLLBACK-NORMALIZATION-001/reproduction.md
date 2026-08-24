# Reproduction

## Expected

對 PR #53 的 exact base `92f4ba8388ecf1ef1f3407db6c49cef62f6ee196` 與
reviewed head `4ebd834702d286ba1baf405e55f5a01035750e80` 建立 audit-only
Merge Gate 後，`merge verify --skip-local-checks` 應先通過 rollback contract，並只因
fresh protected-review receipt 尚未存在而 fail closed。

## Actual

在 clean detached audit head `9b382612bdf7d83efa35a88f1a7560ce4c9f5815` 執行時，驗證器
於 receipt 檢查前回傳 `rollback record is missing or incomplete`，exit status 3。

## Deterministic steps

1. 從本機 repository 建立不含 hardlink 的隔離 clone，checkout exact audit head
   `9b382612bdf7d83efa35a88f1a7560ce4c9f5815`。
2. 設定該 checkout 的 `src` 為 `PYTHONPATH`，使用已驗證本機 venv Python。
3. 執行 `python -m sddgov.cli merge verify <isolated-checkout> --base-ref
   92f4ba8388ecf1ef1f3407db6c49cef62f6ee196 --skip-local-checks`。
4. 確認輸出與 `shareable/artifacts/terminal--red.log` 相同，且 clean detached
   worktree 上 exit status 為 3。

## Environment and preconditions

Linux aarch64、Python 3.11.15、sddgov 0.2.0-experimental.9；branch
`codex/af26-trusted-runner`，Red 來源 commit `9b382612bdf7d83efa35a88f1a7560ce4c9f5815`。
隔離 clone 不讀 credential、不連線 GitHub、不執行 Runner／推論／部署。
