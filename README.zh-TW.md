# Agentic SDD Governance

這是一套給自主軟體開發 Agent 使用的「授權、證據與風險治理層」。

日常工作不需要讀完整 Repo，只載入：

```text
精簡 Policy Kernel＋專案 Profile＋目前 Work Package＋相關 Playbook
```

除錯採用：

```text
Red → Evidence → Fix → Green → Proof
```

原始證據只放在本機 `private/raw`，經 Local Redaction Gateway 處理後，才會進入 `shareable/artifacts`。CLI 不會把資料自動貼到 Issue 或 PR，只會生成可人工檢查的 Evidence Block。

快速入口：

- 治理核心：`core/POLICY_KERNEL.md`
- 開發 Skill：`skill/agentic-sdd-governance/SKILL.md`
- Evidence 設計：`docs/EVIDENCE_DRIVEN_SDD.md`
- 安全遮罩：`redaction/LOCAL_REDACTION_GATEWAY.md`
- CLI：`evidence init|collect|redact|transition|verify|attach`

目前版本是 `v0.2.0-experimental`。Benchmark fixture 只證明測試框架能運作，不代表已實證優於其他開發流程。
