# Work Package：AF26 程序外 Trusted Runner

## References

- Issue：[#52](https://github.com/zycaskevin/Agentic-SDD-Governance/issues/52)；
  本機追蹤 ID `AF26-EXTERNAL-TRUSTED-RUNNER-001`。
- SDD：`docs/TRUSTED_RUNNER_V0_1.md`
- Evidence：`DEP-AF26-EXTERNAL-TRUSTED-RUNNER-001`、
  `DEP-AF26-PR-LOCAL-GATE-001`
- Risk：L1 security-sensitive preparation；任何真實 operation 仍為 L3。

## Objective Contract

- Outcome：提供 socket-activated Trusted Runner 的 rehearsal reference implementation
  與 dedicated non-root UID production contract，完成 peer／bootstrap／sealed FD／
  exact approval／secret ordering／signed result；production 在 cgroup v2 descendant
  containment 與 FD-bound runtime chain 完成前 hard-deny。
- Success：synthetic rehearsal 全鏈路通過；source manifest／profile 內容可重算；
  所有 caller forgery、replay、TOCTOU、timeout 與 cleanup attack tests fail closed；
  `mode=production` 固定回傳 `production_cgroup_containment_required`。
- Guardrails：不讀真實 credential、不使用 Owner key、不執行 Hermes／network／
  inference／Production／Promotion／Gate Enforce／deploy。
- Keep：v1.2 Hard Gates、Merge Gate 與既有 CLI 行為不變；完整回歸與 independent
  security review 全綠。
- Rollback：若 Runner 可在 same-UID production、未耗用 approval 前讀 secret、
  接受 caller path／argv／env，或回傳敏感資料，回滾本 Work Package。

## Scope

- `src/sddgov/trusted_runner.py` 與 bounded CLI surface。
- Trusted Runner request／result／bootstrap schemas 與 packaged resources。
- Synthetic runner harness、adversarial tests、中文 docs、DEP 與跨 repo contract notes。
- 非範圍：service account／systemd／`/etc`／`/var/lib` 配置、Owner signer、真實
  credential、Hermes Live UAT、網路、費用、runtime／product 發布與部署；本次只建立
  source branch、Issue 與 PR 工程紀錄。

## Verification

- Red：`sddgov.trusted_runner` import 與 CLI command 不存在。
- Green：targeted／full tests、Ruff、compileall、fresh Wheel、validate、doctor、CI
  Local Green、rollback drill、independent authentication review、DEP strict Proof。

## Claim

- Owner：2026-08-23 回覆「繼續」，授權 AF26 離線開發並同意將本可信宿主納入
  修改範圍；不是 concrete L3 operation approval。2026-08-24 明確確認目標 repository
  為公開，並批准公開推送 AF26 原始碼、Trusted Runner 架構與安全驗證內容，以及建立
  公開 Issue／PR。
- Builder：Codex。
- Status：Rehearsal Runner、production hard-deny、Schema、Agent Factory 0.3 串接、
  synthetic rehearsal、完整回歸與 Wheel／fresh doctor 均已完成；independent
  security review blocking-free；兩個 DEP 均已進入 Proof 且 strict verification 通過。
