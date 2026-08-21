# Agentic SDD Governance

[English](README.md) | [繁體中文](README.zh-TW.md)

Agentic SDD Governance（SDG）是一套給自主軟體開發 Agent 使用的「授權、證據與風險治理層」。它不是另一個會替你寫程式的 Agent，而是讓 Codex、Hermes 等 Agent 知道：哪些工作可以自主完成、什麼時候必須停下來、除錯要收集哪些證據，以及合併前如何證明結果。

> 目前屬於 experimental 版本。它能安裝、驗證與執行，但不應把內建 Benchmark fixture 解讀成已證明優於其他開發流程。

SDG v1.2 Hard Gates 已把三個剩餘信任缺口改為可執行 Gate：未知／危險 Action 不能自稱 L1、L3 只接受可信 Owner 簽章且一次性消耗的 Receipt、Merge 前必須執行 Local Green、DEP、Redaction、Rollback 與 Protected-file Review 驗證。詳見 [`docs/HARD_GATES_V1_2.md`](docs/HARD_GATES_V1_2.md)。

## 30 秒看懂

在 Source checkout 直接執行：

```bash
./demo/run.sh
```

已安裝 CLI 則執行：

```bash
sddgov pilot quick
```

這個完全離線的 synthetic demo 會展示：

```text
例行 L1 工程                         → CONTINUE
偽裝成 L1 的 Production 破壞操作     → BLOCKED
Evidence 內的 synthetic credential   → REDACTED
未審查的二進位 Evidence              → BLOCKED
Agent 安裝與 strict DEP              → VERIFIED
```

Demo 不使用網路、Credential、真實使用者、Production 或特權服務。

## Runtime 模型

日常任務只載入最小必要內容：

```text
精簡 Policy Kernel
  + 一個專案 Profile
  + 目前 Work Package
  + 當下需要的 Playbook
```

除錯與 Regression 採用：

```text
Red → Evidence → Fix → Green → Proof
```

原始證據只留在本機 `private/raw`。原始二進位證據一律不得進入 `shareable/artifacts`；只有經核准的文字摘要或完成遮罩與人工檢查的衍生物才能進入。CLI 只會生成本機 Evidence Block，不會自動把內容貼到 Issue、PR 或外部服務。

## 適合用在哪裡？

- 新功能、Bug fix、Refactor 與 PR Review。
- Codex 或 Hermes 的跨機器標準開發流程。
- 需要保留 Root Cause、Fix Scope、Regression 與 Rollback 證據的專案。
- 想降低 GitHub Actions 重跑與額度浪費的團隊。
- 需要區分 L0–L3 授權邊界的多 Agent 開發。

它不會替你完成 GitHub Billing、正式部署、MFA、付款、Production 資料操作或其他 Owner 才能授權的外部行為。

## 安裝 CLI

### 快速試用路徑

RC 發布到 PyPI 後，以獨立環境安裝精確 pre-release 版本：

```bash
python3 -m venv .venv-sddgov
.venv-sddgov/bin/python -m pip install --pre 'agentic-sdd-governance==0.2.0rc1'
.venv-sddgov/bin/sddgov --version
.venv-sddgov/bin/sddgov pilot quick
```

這條路徑適合 synthetic 評估。正式受治理的 Repository 應鎖定已審查的精確版本，不要自動漂移到下一個 RC。

### 可控驗證路徑

Linux x86_64／CPython 3.12 的受治理離線環境，從同版本 GitHub Release 下載包含 hash-locked 執行期依賴的 bundle 與 checksum，讓機器核對壓縮檔及其完整清單：

```bash
set -eu
mkdir -p sdg-release
gh release download v0.2.0rc1 \
  --repo zycaskevin/Agentic-SDD-Governance \
  --pattern '*-offline-linux-x86_64-py312.zip' \
  --pattern 'SHA256SUMS.txt' \
  --dir sdg-release

archive_count=$(find sdg-release -maxdepth 1 -type f -name '*-offline-linux-x86_64-py312.zip' | wc -l | tr -d ' ')
test "$archive_count" -eq 1
verified_archive=$(find sdg-release -maxdepth 1 -type f -name '*-offline-linux-x86_64-py312.zip' -print -quit)
(cd sdg-release && rg "  $(basename "$verified_archive")$" SHA256SUMS.txt > offline.SHA256SUMS)
(cd sdg-release && test "$(wc -l < offline.SHA256SUMS | tr -d ' ')" -eq 1)
(cd sdg-release && sha256sum -c offline.SHA256SUMS)
python3.12 -c 'import sys; assert sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12)'
python3.12 -m zipfile -e "$verified_archive" sdg-release/extracted

bundle_count=$(find sdg-release/extracted -mindepth 1 -maxdepth 1 -type d -name '*-offline-linux-x86_64-py312' | wc -l | tr -d ' ')
test "$bundle_count" -eq 1
bundle_root=$(find sdg-release/extracted -mindepth 1 -maxdepth 1 -type d -name '*-offline-linux-x86_64-py312' -print -quit)
(cd "$bundle_root" && sha256sum -c SHA256SUMS.txt)
wheel_count=$(find "$bundle_root/distributions" -maxdepth 1 -type f -name '*-py3-none-any.whl' | wc -l | tr -d ' ')
test "$wheel_count" -eq 1
project_wheel=$(find "$bundle_root/distributions" -maxdepth 1 -type f -name '*-py3-none-any.whl' -print -quit)

python3.12 -m venv .venv-sddgov
.venv-sddgov/bin/python -m pip install \
  --no-index --find-links "$bundle_root/wheelhouse" --require-hashes \
  -r "$bundle_root/requirements-governance.lock"
.venv-sddgov/bin/python -m pip install --no-index --no-deps "$project_wheel"
.venv-sddgov/bin/sddgov --version
.venv-sddgov/bin/sddgov pilot quick
```

RC1 的離線依賴 bundle 刻意鎖定平台；macOS、Windows、其他架構或 Python 版本，在相符 bundle 發布前應於隔離的連網環境安裝精確 PyPI RC。Private Release 下載才需要先執行 `gh auth login`。不要把 Token 或 checksum 貼到聊天中請人判斷。

### Contributor 原始碼路徑

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/sddgov validate .
./demo/run.sh
```

### 安裝到 Codex 專案

```bash
SDDGOV_BIN=.venv-sddgov/bin/sddgov  # Contributor 原始碼路徑請改用 .venv/bin/sddgov
"$SDDGOV_BIN" setup-agent /absolute/path/to/project \
  --agent codex \
  --profile team-standard

"$SDDGOV_BIN" doctor /absolute/path/to/project
"$SDDGOV_BIN" status /absolute/path/to/project
```

重新開啟一個 Codex task，Agent 應能從 `.agents/skills/agentic-sdd-governance/SKILL.md` 發現 Skill。你可以直接說：

```text
請使用 Agentic SDD Governance 處理這個 Bug，依照 Red → Evidence → Fix → Green → Proof 完成。
```

### 安裝到 Hermes 專案

```bash
.venv-sddgov/bin/sddgov setup-agent /absolute/path/to/project \
  --agent hermes \
  --profile team-standard

.venv-sddgov/bin/sddgov doctor /absolute/path/to/project
```

Hermes Adapter 與檔案安裝已支援；不同 Hermes Host 是否會自動發現並觸發 Skill，仍要在實際 GB10／Hermes Runtime 做一次 Pilot。`doctor` 通過只證明檔案與 Hash 正確，不等於 Agent 行為已完整驗收。

## 安裝器會修改什麼？

`setup-agent` 只管理下列範圍：

```text
AGENTS.md                                      標記區塊
.gitignore                                     raw evidence 忽略區塊
.agents/skills/agentic-sdd-governance/        可被 Agent 發現的 Skill
.agentic-sdd-governance/                       版本化治理資源
.sddgov/                                       專案治理狀態
```

既有 `AGENTS.md` 與 `.gitignore` 的其他內容會保留。若受管理檔案被手動修改，安裝、升級或解除安裝會 fail closed，要求先檢查差異。

## 三種 Profile

| Profile | 適合情境 | 主要特性 |
|---|---|---|
| `solo-fast` | 個人、低風險專案 | 優先速度；敏感範圍仍會升級 |
| `team-standard` | 一般團隊與多 Agent 開發 | Issue／PR、獨立 Review、L1 完整 DEP |
| `regulated` | 高稽核、法規或高風險環境 | Provenance、第二風險 Review、嚴格 Redaction 與 L3 Proof |

## L0–L3 怎麼判斷？

| 等級 | 例子 | Agent 行為 |
|---|---|---|
| L0 | 文件、小型非 Regression 修正、明確局部工作 | 自主完成並提供 targeted proof |
| L1 | Regression、跨模組、Auth、Reliability、資料流 | 先收證據，建立完整 DEP，自主完成已核准範圍 |
| L2 | 產品行為、Quota、Pricing、Privacy、Public API 改變 | 可研究與做安全 Prototype，但需一個明確 Owner 決策 |
| L3 | Production、付款、刪除正式資料、Credential、MFA | 只準備 Dry run、Rollback 與 Proof；具體操作需明確授權 |

證據能提高信心，但不會自動提高 Agent 權限。

## Evidence 快速範例

以下命令可使用獨立的 `evidence` 入口，也可以寫成 `sddgov evidence ...`：

```bash
evidence init --issue ISSUE-128 --risk L1 --sdd FAMILY-03

evidence collect evidence/DEP-... \
  --collector terminal \
  --input failing-test.log

evidence redact evidence/DEP-...
evidence transition evidence/DEP-... evidence
```

接著完成 DEP 內的 Root Cause Hypothesis、Fix Scope、Regression Evidence、Verification 與 Rollback，再依序推進：

```bash
evidence transition evidence/DEP-... fix
evidence transition evidence/DEP-... green
evidence transition evidence/DEP-... proof

evidence verify evidence/DEP-... --strict
evidence attach evidence/DEP-... --target pr
```

Collector 是「如何安全收集證據」的 Playbook；目前 CLI 的 `collect` 會匯入既有輸出，不會自動登入 Browser、Supabase 或 Production。可用路由包括：

- Browser／Console／Network／Playwright trace。
- Flutter／Android Logcat。
- Supabase local stack／Docker。
- Terminal／Tests／Build／Git。

## CI Cost Guard

每個專案用 `.sddgov/ci-cost-guard.json` 宣告本機 Green Gate 與 Hosted CI 預算：

```bash
sddgov ci verify .
sddgov ci local-gate .
```

它會檢查 Workflow 是否具備 read-only permissions、同一 PR／ref 的 stale-run cancellation、Draft PR 不配置 Runner，以及每個 Job 的 timeout。它不會替你改 GitHub Billing budget，也不會因省錢而弱化測試。

## 自主執行與 Artifact Integrity

預設狀態是 `CONTINUE`。經 autonomy classifier 判定為已授權 L0/L1 後，可由 Repo、SDD、Decision／ADR、Tests、CI 或 Tools 驗證的證據問題不得詢問產品負責人；未解決的 L2 產品／額度／價格／隱私／Public API 決策、具體 L3 操作、Operational Action 與 Necessary UAT 仍須使用 `ACTION REQUIRED`。完整規格見 [SDG Autonomous Development v1.2](docs/AUTONOMOUS_DEVELOPMENT_V1_2.md)。

SHA-256 保留為 Invisible Infrastructure，由機器產生與驗證：

```bash
sddgov artifact lock dist/package.whl --release release-X --output release.lock
sddgov artifact verify dist/package.whl --lock release.lock
```

Match 會繼續；Mismatch 會自動阻擋該 Artifact 並進入調查，不會要求使用者複製或貼回 Hash。

## 更新與移除

升級 CLI 後先執行 `doctor`，再審查受管理檔案。只有確認要替換 SDG 管理的內容時才使用 `--force`：

```bash
sddgov doctor /absolute/path/to/project
sddgov setup-agent /absolute/path/to/project \
  --agent codex \
  --profile team-standard \
  --force
```

解除安裝：

```bash
sddgov uninstall-agent /absolute/path/to/project
```

`.sddgov` 與 `evidence` 預設保留，避免治理事件與除錯證據被靜默刪除。

## 完整文件

- [繁中完整使用指南](docs/USER_GUIDE.zh-TW.md)
- [Agent 安裝、升級與移除](docs/AGENT_INSTALLATION.md)
- [Evidence-Driven SDD 設計](docs/EVIDENCE_DRIVEN_SDD.md)
- [CI Cost Guard](docs/CI_COST_GUARD.md)
- [SDG Autonomous Development v1.2](docs/AUTONOMOUS_DEVELOPMENT_V1_2.md)
- [Local Redaction Gateway](redaction/LOCAL_REDACTION_GATEWAY.md)
- [Owner Key Ceremony 與金鑰復原](docs/OWNER_KEY_CEREMONY.md)
- [L3 Broker／WSL2／macOS 操作](docs/L3_BROKER_OPERATIONS.md)
- [Rollback v3、Squash 與 Break-glass](docs/ROLLBACK_OPERATIONS.md)
- [公開發布檢查清單](docs/PUBLIC_RELEASE_CHECKLIST.zh-TW.md)
- [Roadmap](docs/ROADMAP.md)
- [Security Policy](SECURITY.md)
- [貢獻指南](CONTRIBUTING.md)

## Repository 地圖

- `core/`：每次工作必讀的小型 Policy Kernel。
- `profiles/`：三種治理重量。
- `skill/`：薄型觸發入口與按需載入路由。
- `schemas/`：DEP、Collector 與治理資料契約。
- `collectors/`：不同 Stack 的 Evidence Playbook。
- `redaction/`：本機分享邊界。
- `src/sddgov/`：可執行 CLI。
- `demo/`：離線 30 秒首次體驗。
- `services/`：systemd 與 launchd Broker 範本。
- `templates/`、`.github/`：Issue、PR、Commit、Changelog 與 Work Package 範本。
- `benchmarks/`：成對 Debugging 評估 Harness。

## 發布與授權狀態

- `v0.2.0-experimental.8` 是最近完成的 experimental release。
- `0.2.0rc1` 是已準備的 PyPI pre-release 目標；正式發布仍是明確的外部 Release Action。
- 專案使用 Apache License 2.0，詳見 [LICENSE](LICENSE)。
- 公開前仍需由 Owner 接受 Git 歷史、作者資訊、Release Notes 與 experimental 風險；詳見 [公開發布檢查清單](docs/PUBLIC_RELEASE_CHECKLIST.zh-TW.md)。
- 本專案沒有複製 BugEzy 原始碼、資產、Template 或 Schema；來源聲明見 [Baseline Provenance](docs/BASELINE_PROVENANCE.md) 與 [Third-Party Notices](THIRD_PARTY_NOTICES.md)。

## 已知限制

- Local Redaction Gateway 具有 10 MiB 單檔上限與跨 chunk 串流，但仍不是法律上的匿名化認證。
- Screenshot、HAR、Trace ZIP、Video、Database dump 等二進位證據在人工審查前會 fail closed。
- Benchmark fixture 只驗證 Harness，不能宣稱 Evidence-Driven Debugging 已實證勝出。
- Codex Skill discovery 與 Hermes 檔案安裝已有驗證；新 Agent 行為與 GB10 Hermes Runtime 仍需 Pilot。
- 專案目前不是正式穩定版；使用真實敏感資料前仍須完成 Owner key ceremony、Broker readiness 與實際 Runtime pilot。
