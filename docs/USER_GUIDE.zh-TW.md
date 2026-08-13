# Agentic SDD Governance 繁中完整使用指南

本文件供實際安裝、跨機器導入與日常操作使用。Agent 執行任務時不需要整份載入；它只應依 Skill 路由讀取 Policy Kernel、單一 Profile、目前 Work Package 與相關 Playbook。

## 1. 安裝前準備

最低需求：

- Python 3.10 或更新版本。
- 要操作的 Git Repository。
- 安裝 Private GitHub Release 時，需要 GitHub CLI `gh` 與 Repo 權限。
- Codex 或 Hermes 的實際執行環境。

先確認：

```bash
python3 --version
git --version
gh --version
```

不要把 GitHub Token、密碼、OTP、Private Key 或 Production dump 貼進聊天、Issue 或文件。

## 2. 取得安裝套件

### 方法 A：從 GitHub Release 下載 wheel（建議）

Private Repo 必須先登入：

```bash
gh auth login -h github.com
gh auth status -h github.com
```

下載並核對 Checksum：

```bash
mkdir -p sdg-release
gh release download v0.2.0-experimental.3 \
  --repo zycaskevin/Agentic-SDD-Governance \
  --pattern '*.whl' \
  --pattern 'SHA256SUMS.txt' \
  --dir sdg-release

wheel_name=$(find sdg-release -maxdepth 1 -type f -name '*.whl' -print -quit)
test -n "$wheel_name"
(cd sdg-release && rg "  $(basename "$wheel_name")$" SHA256SUMS.txt > wheel.SHA256SUMS)
(cd sdg-release && test -s wheel.SHA256SUMS)
(cd sdg-release && shasum -a 256 -c wheel.SHA256SUMS --strict)
```

macOS 內建 `shasum`。Linux 可把最後一行改成 `sha256sum -c wheel.SHA256SUMS`。這段流程會先確認 wheel 存在、再從 Registry checksum 取出該 wheel 的唯一紀錄並由機器比對；不需要把 Digest 複製或貼給 Agent。

安裝到獨立 Virtual Environment：

```bash
python3 -m venv .venv-sddgov
.venv-sddgov/bin/python -m pip install sdg-release/*.whl
.venv-sddgov/bin/sddgov --version
```

### 方法 B：從原始碼安裝

```bash
git clone https://github.com/zycaskevin/Agentic-SDD-Governance.git
cd Agentic-SDD-Governance
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/sddgov validate .
```

Private Repo 的 Clone 同樣需要 GitHub 權限。

### 方法 C：離線 GB10／Hermes

在可連網機器下載 ZIP、wheel、bundle 與 `SHA256SUMS.txt`，驗證 Checksum 後用受信任通道複製到 GB10。

使用 wheel 不需要 Git History。需要完整 Git History 時可從 bundle Clone：

```bash
git clone agentic-sdd-governance-v0.2.0-experimental.3.bundle \
  Agentic-SDD-Governance
```

不要用來路不明或未核對 SHA-256 的壓縮檔。

## 3. 導入既有專案

### Codex

```bash
sddgov setup-agent /absolute/path/to/project \
  --agent codex \
  --profile team-standard
sddgov doctor /absolute/path/to/project
sddgov status /absolute/path/to/project
```

完成後重新開啟 Codex task，讓它從 Repo 根目錄重新探索 `AGENTS.md` 與 `.agents/skills/`。

建議首次測試 Prompt：

```text
請告訴我這個 Repo 使用哪個 Governance Profile、開發前要讀哪些最小文件，先不要修改程式。
```

正確行為應包含：

1. 發現 `agentic-sdd-governance` Skill。
2. 讀取 Policy Kernel。
3. 只選一個 Profile。
4. 尋找目前 Work Package 與相關 Playbook。
5. 不把整個治理 Repo 全部塞進 Context。

### Hermes／GB10

```bash
sddgov setup-agent /absolute/path/to/project \
  --agent hermes \
  --profile team-standard
sddgov doctor /absolute/path/to/project
```

再用全新的 Hermes Session 執行相同探索測試。不同 Hermes Host 的 Skill discovery 行為可能不同；若 Host 沒有自動載入 Repo Skill，請把專案根目錄的 `AGENTS.md` 設為 Workspace Instruction 入口，但不要把整套治理內容複製到 `SOUL.md`。

`SOUL.md` 適合人格、態度與互動風格；專案規則放 `AGENTS.md`，開發 SOP 放 Skill，機器檢查交給 `sddgov`。

## 4. 選擇 Profile

### `solo-fast`

適合個人與低風險 Prototype。一般工程判斷可自主進行，但 Credential、Production、Privacy、付款等敏感操作仍會升級。

### `team-standard`

預設建議。要求 Issue／PR、獨立 Review、Local Green Gate，Regression 與跨模組問題使用完整 DEP。

### `regulated`

適合需要 Provenance、第二風險 Review、嚴格 Redaction 與完整 L3 Rollback Proof 的環境。它不是法規認證，仍須由組織自行完成合規評估。

## 5. 日常功能開發

SDG v1.2 預設 `CONTINUE`。Issue、Branch、Commit、feature-branch Push、PR、Review、測試、CI、可恢復 Retry、Integrity verification 與通過必要 Gate 後的 L0/L1 Merge都是工程操作，不是 Owner Approval 點。只有 unresolved L2、concrete L3、Operational Action 或 Necessary UAT 才能輸出嚴格的 `ACTION REQUIRED`。詳見 [`AUTONOMOUS_DEVELOPMENT_V1_2.md`](AUTONOMOUS_DEVELOPMENT_V1_2.md)。

建議循環：

```text
SDD
→ Work Package
→ 可執行驗證
→ 實作
→ Local Review／Tests
→ PR
→ Independent Review
→ CI
→ Proof
→ 下一個未阻塞 Work Package
```

建立 Work Package 時，明確寫出 Outcome、Success metric、Guardrails、Non-scope、Evidence 與 Rollback condition。Issue、Commit、PR、Review、CI 與 Evidence 都是工程紀錄，不是每一步都重新向 Owner 請示。

## 6. Bug 與 Regression

### Red

先保存預期與實際行為、重現步驟、失敗測試、Commit、Runtime 與環境。不要先改程式再回頭猜原始症狀。

### Evidence

只選能區分 Root Cause 假設的 Collector。原始輸出放 `private/raw`，不要傾倒無關 Log。

```bash
evidence init --issue ISSUE-123 --risk L1 --sdd CAP-03
umask 077
mkdir -p evidence/DEP-.../private/raw
chmod 700 evidence/DEP-.../private/raw
your-test-command > evidence/DEP-.../private/raw/failure.log 2>&1
evidence collect evidence/DEP-... --collector terminal --input evidence/DEP-.../private/raw/failure.log
evidence redact evidence/DEP-...
evidence transition evidence/DEP-... evidence
```

### Fix

寫一個可被證偽的 Root Cause Hypothesis，定義最小 Fix Scope、Non-scope 與 Blast radius。普通 Bug fix 不會只因修好後畫面不同就自動變成 L2；但若修改了產品承諾、Quota、Pricing、Privacy 或 Public API，就必須進入 L2 Decision Package。

### Green

重跑原始失敗檢查，再跑受影響邊界的 Regression checks。不得刪除或放寬失敗測試來製造 Green。

### Proof

完成 Verification、Regression、Limitations 與 Rollback，確認外部紀錄只引用 `shareable/artifacts`：

```bash
evidence verify evidence/DEP-... --strict
evidence attach evidence/DEP-... --target pr
```

`attach` 只輸出本機 Markdown，不會直接貼到 GitHub。

## 7. Collector 路由

| 問題 | Collector ID | Playbook |
|---|---|---|
| Browser UI、Console、Network、DOM、E2E | `browser-console`、`browser-har`、`playwright-trace` | `collectors/browser-playwright.md` |
| Flutter／Android Runtime | `flutter-log`、`android-logcat` | `collectors/flutter-android.md` |
| Supabase local／Container | `supabase-log`、`docker-log` | `collectors/supabase-docker.md` |
| Test、CLI、Build、Diff、Blame、Bisect | `terminal`、`git` | `collectors/terminal-git.md` |

Screenshot 只能證明症狀，不能單獨證明 Root Cause。HAR、Trace ZIP、Video、Screenshot、Database dump 等二進位證據，必須產生人工檢查過的安全衍生物才能分享。

## 8. CI Cost Guard

從 `.agentic-sdd-governance/templates/CI_COST_GUARD.json` 建立 `.sddgov/ci-cost-guard.json`，再把 `local_green.commands` 改成專案自己的 Shell-free argument arrays。

```bash
sddgov ci verify .
sddgov ci local-gate .
```

Hosted CI 預設原則：

- 同一 Work Package 最多一個 current run。
- 同一 Revision 最多重跑一次，而且必須有 Runner／Network／Provider transient failure 證據。
- Code／Test／Migration／Config failure 必須先在本機重現並產生新 Revision。
- Draft PR 不配置 Runner。
- 使用 concurrency 取消 stale runs。
- 每個 Job 有 `timeout-minutes`。
- 預設 `permissions: contents: read`。

CI Cost Guard 不會設定 GitHub Billing budget、自架 Runner 或 Production Workflow，這些仍是 Owner Action。

## 9. 其他治理命令

初始化只有治理狀態、尚未安裝 Agent Adapter 的專案：

```bash
sddgov init . --profile team-standard
```

Claim Work Package：

```bash
sddgov claim WP-123 --agent codex --ttl-minutes 120 --path .
```

追加 Governance event：

```bash
sddgov event local_green_passed \
  --risk L1 \
  --payload '{"tests":"passed"}' \
  --path .
```

排入一個有界的 Owner Action：

```bash
sddgov external-action BILLING-001 \
  --summary 'Confirm GitHub Actions budget' \
  --risk L3 \
  --owner Arthur \
  --path .
```

這個命令只建立 Queue record，不會替 Owner 操作 Billing。

## 10. 升級

1. 下載並驗證新的 wheel。
2. 在 CLI Virtual Environment 升級套件。
3. 對目標專案執行 `doctor`。
4. 審查受管理檔案差異。
5. 確認後才用 `setup-agent ... --force` 更新 SDG 管理的檔案。
6. 再次執行 `doctor` 與專案 Local Green Gate。

不要用 `--force` 覆蓋不屬於 SDG 的 `AGENTS.md` 或 `.gitignore` 內容；安裝器只應處理 Manifest 與標記區塊內的檔案。

## 11. 解除安裝

```bash
sddgov uninstall-agent /absolute/path/to/project
```

若管理檔案被修改，命令會停止。審查後可使用 `--force` 移除受管理內容。`.sddgov` 與 `evidence` 會保留；若之後真的要刪除，請先完成保存期限、備份、敏感資料與 Recovery 評估。

## 12. 常見問題

### GitHub 網址顯示 404

Private Repo 對未登入或沒有權限的使用者會故意回傳 404。請在同一個 Browser 登入有權限的帳號，或使用：

```bash
gh auth login -h github.com
gh release download <tag> --repo <owner/repo>
```

### `sddgov: command not found`

確認使用安裝 CLI 的 Virtual Environment：

```bash
.venv-sddgov/bin/sddgov --version
```

### `doctor` 回報 Hash 不一致

先查看哪個受管理檔案被修改。保留需要的專案規則，再決定是否執行 `setup-agent --force`；不要直接刪除 Manifest 或重裝掩蓋差異。

### Evidence 無法 Attach

常見原因包括尚未進入 Proof、缺少必填文件、Redaction 未完成、Binary artifact 尚未人工 Review、L2 Decision Package 未核准，或 L3 具體操作未取得明確授權。

### Hermes 有檔案但沒有觸發 Skill

`doctor` 只驗證安裝完整性。請用全新 Hermes Session 測試 Host discovery；必要時將 Repo 根目錄 `AGENTS.md` 設為 Workspace Instruction 入口。不要把完整治理文件塞進 `SOUL.md`。

## 13. 安全邊界

- `evidence/**/private/raw/` 必須被 Git ignore。
- 不要在 Issue、PR、Chat、Screenshot 或文件放 Token、Cookie、OTP、Private Key 或 Production dump。
- Redactor 是降低意外洩漏的 MVP，不是法律匿名化認證。
- 更多 Evidence 不會授權更高風險的行動。
- 付款、正式資料刪除、Credential 與 MFA 均須明確 Owner 授權；正式部署只有在屬於 L3、破壞性、高權限、Secret／Permission boundary 變更、不可逆或無可靠復原時需要新的明確授權。符合已記錄 Baseline 且八項機器 Guardrails 全通過的可逆 L1 部署可自主執行。

公開 Repository 前，請完成 [`PUBLIC_RELEASE_CHECKLIST.zh-TW.md`](PUBLIC_RELEASE_CHECKLIST.zh-TW.md)。
