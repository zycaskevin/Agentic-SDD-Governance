# 公開發布檢查清單

本文件用來判斷 Private Repository 是否適合改為 Public。完成技術檢查不等於自動授權公開；Repository visibility、License 接受與個人資訊揭露仍是 Owner 決策。

## 2026-08-13 準備度 Snapshot

### 已確認

- Repository 目前為 Private；`v0.2.0-experimental.3` 是已發布的 Pre-release，不是 Draft。
- 根目錄存在 Apache License 2.0，GitHub 可辨識為 `Apache-2.0`。
- `docs/BASELINE_PROVENANCE.md` 記錄 Canonical baseline 與重建界線。
- `THIRD_PARTY_NOTICES.md` 聲明 BugEzy 只提供概念啟發，沒有複製其 Source、Asset、Template、Schema 或 Brand material。
- Tracked files 沒有 `private/raw`、ZIP、wheel、bundle、build、dist 或 outputs artifact。
- `evidence/**/private/raw/` 受到 `.gitignore` 保護。
- 對目前 Tracked worktree 與全部 Git commits 執行常見 GitHub、AWS、Google、Slack、Stripe Token 與 Private Key Header 的針對性 Pattern scan，沒有命中。
- 從官方 `gitleaks/gitleaks` Release 取得固定版本 `v8.30.1`，以官方 SHA-256 驗證 Darwin ARM64 Binary 後掃描全部 7 個 Git commits；結果為 0 findings。
- 重新從 GitHub Release 下載 `v0.2.0-experimental.3`，四個封裝檔均通過 `SHA256SUMS.txt`；解開後的 ZIP、wheel、sdist 與 bundle Git History 經 Gitleaks 掃描均為 0 findings。
- GitHub Actions 使用 read-only default permissions、concurrency cancellation、Draft PR skip 與 Job timeout。

### 必須由 Owner 決定

1. 是否同意所有目前與未來程式碼依 Apache License 2.0 對外授權。
2. 是否接受完整 Git History 公開，包括 Commit author 使用的個人 Email。具體值請在本機執行 `git log --all --format='%an <%ae>' | sort -u` 檢查。
3. 是否接受 Release Notes 中出現 MyHermes、Vault-Agent-Memory、Piku 等專案名稱與驗證摘要。
4. 是否接受 experimental 軟體公開後可能被誤用；README 必須保留「非穩定版、非合規認證、Benchmark 非優越性證明」限制。
5. 是否現在把 Repository visibility 從 Private 改為 Public。

### 公開前建議補強

- 在真正切換 Visibility 前，從乾淨 Clone 對最終 Commit 與最終 Release assets 再執行一次 Gitleaks；目前通過結果只涵蓋本 Snapshot 所列版本。
- 將 `actions/checkout`、`actions/setup-python` 等 Workflow Action pin 到完整 Commit SHA，降低 mutable tag 供應鏈風險。
- 公開後立即啟用 GitHub Secret scanning、Push protection、Dependabot alerts 與 Private vulnerability reporting（依 GitHub Plan 可用功能為準）。
- 建立 Branch ruleset，保護 `main`、要求 Governance check 與 Review。
- 公開前用已授權 CLI 驗證 Repo、Release、ZIP、wheel 與 checksum；未登入 Browser 的公開可見性測試放在 Visibility 變更後執行。
- 從全新 Temporary directory 安裝 wheel，分別執行 Codex／Hermes `setup-agent` 與 `doctor`。
- 再次確認 Release asset SHA-256 與 `SHA256SUMS.txt` 一致。

## 不得公開的內容

- `evidence/**/private/raw/`。
- Token、Cookie、Authorization Header、Password、OTP、Private Key。
- Production Database dump、未遮罩 Log、患者／付款／客戶資料。
- 未取得再散布權利的第三方 Source、Asset、Prompt、Template、Schema 或 Brand material。
- 仍含敏感內容的 Screenshot、HAR、Playwright Trace、Video、Crash archive 或其他 Binary evidence。

## 公開前命令清單

```bash
# Repo 與治理驗證
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m sddgov.cli validate .

# CI Cost Guard
PYTHONPATH=src python3 -m sddgov.cli ci verify .
PYTHONPATH=src python3 -m sddgov.cli ci local-gate .

# 檢查作者資訊
git log --all --format='%an <%ae>' | sort -u

# 確認沒有意外追蹤 raw evidence 或 build artifact
git ls-files | rg '(^|/)(private/raw|outputs|dist|build|work)/|\.(zip|whl|bundle)$'

# 查看準備公開的完整差異
git status --short
git diff --stat
```

若最後一個 artifact 命令沒有輸出，代表指定類型沒有被追蹤；它不等於完整 Secret scan。

## Public 後驗收

1. 未登入 Browser 能開啟 Repository 首頁。
2. 未登入 Browser 能開啟 Release 頁並下載五個自訂 Asset。
3. Checksum 驗證通過。
4. README 的繁中、English、User Guide、Security、License 與 Contribution 連結均可用。
5. GitHub Actions 沒有因 Public fork／PR 取得多餘權限或 Secret。
6. Security、Ruleset 與 Dependency settings 已套用。

## Visibility 變更邊界

把 Private Repository 改為 Public 會立刻公開完整 Source、Git History、Issue、Release 與 Commit author metadata。這是 L2 Owner Decision；Agent 可以準備與驗證，但必須取得明確的「將 `zycaskevin/Agentic-SDD-Governance` 改為 Public」授權後才能執行。
