# 修補範圍

## 最小充分變更

新增 service-owned bootstrap、SO_PEERCRED／SCM_RIGHTS wire boundary、exact request／
sealed FD verifier、canonical source／profile 內容重算、approval-first credential pipe、
rehearsal-bounded child lifecycle、production hard-deny 與 signed result。

## 範圍內

- `src/sddgov/trusted_runner.py`、CLI wiring、schemas／packaged resources。
- `tests/test_trusted_runner.py`、SDD、Work Package、DEP 與狀態／changelog。
- 必要的 AF25 cross-repository exact input／launch binding contract。

## 明確非範圍

不配置 service account／systemd／`/etc`／`/var/lib`，不使用 Owner private key／真實
credential，不啟動 Hermes／Provider／network，不發布或部署。

## 影響半徑

新增 CLI surface；既有 autonomy、merge、reviewer、evidence 與 L0/L1 行為保持不變。
Production mode 無論 bootstrap 值皆固定 fail closed，直到 cgroup v2 descendant
containment 與 FD-bound runtime execution chain 完成。
