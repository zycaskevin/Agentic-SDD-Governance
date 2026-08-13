# 貢獻指南

感謝你協助改進 Agentic SDD Governance。這是一個 experimental 專案；請讓每個變更都可重現、可 Review、可回復。

## 開始前

1. 先建立或認領一個 Issue，說明 Outcome、Scope 與 Non-scope。
2. 讀取 `core/POLICY_KERNEL.md`、一個適用 Profile、目前 Work Package 與相關 Playbook。
3. Bug 或 Regression 使用 `Red → Evidence → Fix → Green → Proof`。
4. 不要提交 Raw evidence、Credential、Production dump 或未授權的第三方內容。

## 本機環境

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m sddgov.cli validate .
```

CI 或 Workflow 變更還必須執行：

```bash
PYTHONPATH=src .venv/bin/python -m sddgov.cli ci local-gate .
```

## Pull Request

- 說明 Issue／SDD、Risk level、Root Cause、Fix Scope 與 Non-scope。
- 列出執行過的命令與結果，不要只寫「已測試」。
- Regression 必須附完整 DEP；只可引用通過 Redaction 的 `shareable/artifacts`。
- 說明 Limitations 與 Rollback。
- 不得為了 Green 而刪除、跳過或弱化必要測試。

## License

除非明確另行聲明，提交到本 Repository 的 Contribution 依 Apache License 2.0 提供。你必須擁有所提交內容的權利，並保留適用的第三方 Attribution 與 License notice。
