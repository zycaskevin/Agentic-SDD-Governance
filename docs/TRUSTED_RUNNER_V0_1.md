# 程序外 Trusted Runner v0.1 SDD

## 狀態與權限

- 工作套件：`WP-AF26-EXTERNAL-TRUSTED-RUNNER-001`。
- 本機實作風險：L1 security-sensitive engineering；Authentication 獨立審查必須通過。
- 真實 credential、Owner-signed L3 receipt、不同 UID service、Hermes／Provider
  process、network、費用與部署均屬另一筆精確 L3／Operational action，本 SDD 不授權。
- v0.1 目前是 rehearsal reference implementation；`mode=production` 在 bootstrap
  載入時固定回傳 `production_cgroup_containment_required`。在 cgroup v2 scope、整個
  cgroup kill、pids／memory／CPU 上限與 FD-bound runtime chain 完成前，不存在 production
  child authority。
- AF25 已固定 Agent Factory 只產生 credential-free、offline-only、
  `launch_permitted=false` 的 sealed capsule；AF26 不得把權限放回 caller process。

## 問題

Python private object、caller-provided executable／trust file 或回傳含 key 的 environment
都不是可信邊界。同一 UID 的 candidate code 可以匯入 private issuer、替換路徑或複製
secret。真正 L3 Runner 必須在 candidate Workspace 與 OS 身分之外持有：

- Owner-controlled bootstrap 與 approver trust source；
- 只允許 service UID 讀取的 credential／result signing key；
- approval decision state；
- child process、timeout、termination 與 cleanup ownership。

## 架構

```text
Agent Factory client UID
  credential-free AF25 request + sealed memfd
               |
               | systemd socket activation / Unix socket + SCM_RIGHTS
               v
dedicated non-root Runner UID（目標 production 架構）
  SO_PEERCRED client verification
  -> service-owned 0600 bootstrap
  -> recompute runner/authority/credential/runtime/isolation bindings
  -> validate exact AF25 request and sealed FD
  -> verify + atomically consume exact Owner-signed L3 receipt
  -> only now open service-owned credential
  -> create unique 0700 isolation and cgroup-v2-owned child scope
  -> enforce fixed runtime argv, environment allowlist and 120-second deadline
  -> terminate/kill, close FDs, zeroize buffer, remove isolation
  -> Ed25519-signed content-safe result
```

## Bootstrap Contract

Bootstrap 必須為 service UID 擁有、0600、單一 hard link、非 symlink regular JSON。
Production mode 目標另要求 service UID 非 root，且不得等於任何 allowed client UID；
v0.1 即使資料符合也一律 hard-deny，不能只靠 process group 進入 production。
Bootstrap 只由 service manager 提供，不能由 wire request 指定，至少包含：

- runner ID、service UID、allowed client UIDs；
- service-owned 0700 state root、0600 trusted approver store；
- result signing private key與對應 public key；
- allowlisted runtime executable absolute path、SHA-256 與固定 argv template；
- credential reference、service-private source path、content SHA-256 與 opaque binding；
- isolation parent 與固定 endpoint／input／output／call／cost／time policy。

Live bootstrap 不接受 `/tmp` credential／state／signing key。Rehearsal bootstrap 可以使用
唯一 0700 `/tmp`、固定 synthetic key 與同 UID，但只接受 `rehearsal_only=true` 且強制
`AGENT_FACTORY_OFFLINE_ONLY=1`，不得形成 production authority。

## Wire Request Contract

Runner 只接受一個長度上限內的 canonical JSON request 與一個以 `SCM_RIGHTS` 傳入的
sealed bundle FD。Socket client UID 必須由 Linux `SO_PEERCRED` 取得，不接受 JSON 宣稱。
Request 必須精確綁定：

- AF25 contract/action/operation/plan hashes；
- Hermes 0.20.4 pinned source、canonical source-tree manifest、五個 managed module 的
  原始 bytes、完整 sealed receipt 與五個 replacement hashes；
- route／containment profile 的完整 canonical 文件與重算 hash；
- Runner、approval authority、credential、runtime、isolation bindings；
- `openai-api／gpt-5.6-sol`、官方 endpoint、4,096 input bytes、1,000 output tokens、
  one call、USD 0.25、120 seconds、zero tools／approval／subagent／auxiliary；
- exact input payload SHA-256 與 bootstrap-owned launch contract SHA-256；
- 新鮮 Ed25519 approval envelope，其 operation ID 必須完全相同。

未知欄位、duplicate JSON key、路徑、argv、environment、secret value、false-valued
安全宣稱或不相符 binding 一律 fail closed。

## Sealed Bundle Contract

- FD 必須是 regular memfd，含 `F_SEAL_WRITE／GROW／SHRINK／SEAL`。
- size／SHA-256／ZIP entry count 必須與 request 完全相符。
- ZIP 不得有 duplicate、absolute、`..`、NUL 或 backslash path。
- ZIP 只能使用 stored、未加密 regular entries，且不得有 size amplification。
- Runner 必須由 manifest 重算整棵 source tree；五個 managed entries 的原始 bytes
  必須符合 containment source hashes，replacement bytes 必須符合 receipt。
- ZIP 名稱集合必須精確等於 source entries、五份 managed originals 與 manifest，
  不能夾帶未綁定內容。
- FD identity、size、seals 與 hash 在 approval 前及 child launch 前重驗。

## Approval 與 Secret Ordering

1. 先驗證 peer、bootstrap、request、bindings、runtime 與 sealed bundle。
2. 將 wire 內 signed envelope 寫入 service-private temporary file，以既有
   `import_operation_approval` 驗簽；已匯入／nonce replay fail closed。
3. 以既有 `evaluate_escalation` 在 decisions lock 內重驗 envelope、operation ID、
   expiry、nonce 與 unused state，第一個 `CONTINUE` 原子耗用。
4. 只有收到 exact `fresh_l3_operation_approval_verified` 後才開啟 credential。
5. Approval 已耗用後任何失敗不得 replay；重試需要新 receipt。

## Child 與 Cleanup Contract

- Caller 不得提供 command、cwd、environment 或 output destination。
- Runner 從 bootstrap 固定 argv template，只允許 `{bundle_fd_path}`、
  `{hermes_home}`、`{input_path}` 與 `{result_path}` 四個受控 placeholder。
- Rehearsal child 使用全新 process group、stdin closed、bounded stdout／stderr capture、
  乾淨 allowlist environment；key 經一次性 pipe 在 child-side exec 前加入 environment，
  永不進入 parent environment 或回傳 caller。
- Rehearsal 逾時先 TERM 再 KILL；任何路徑都關閉 descriptor、抹除 Runner 與 launcher
  持有的 mutable credential buffer、unlink input、移除 isolation root。這個欄位不宣稱
  可以抹除 kernel 或已 exec process 曾持有的所有副本。
- Process group 無法拘束自行 `setsid()` 的逃逸後代，因此 production 必須由 cgroup v2
  scope 擁有完整 descendant lifecycle 並 kill 整個 cgroup；v0.1 在此完成前 hard-deny。
- Result 只含 hashes、usage／exit 類別、approval/runtime/cleanup booleans，並由
  service signing key Ed25519 簽署；不含 output、stderr、secret、path 或 argv。

## 離線驗收

- Rehearsal 以 ephemeral Ed25519 approver／Runner keys、固定 synthetic secret、
  sealed memfd 與 synthetic child 完成 approval -> secret -> child -> cleanup 全鏈路。
- Agent Factory 0.3 request 與 9,925-entry full Hermes bundle 已完成跨 repository
  synthetic rehearsal；signed result 為 completed，且 `inference_applied=false`。
- 攻擊測試覆蓋 same-UID production、root service、wrong peer、bootstrap mode／owner／
  symlink／hardlink、fake binding、duplicate JSON、bundle mutation／missing seals／ZIP
  traversal、approval mismatch／replay／concurrency、secret-before-approval、runtime drift、
  env injection、authority replacement window、profile／source material drift、timeout、
  TERM/KILL 與 cleanup failure。
- Targeted、完整 regression、Ruff、compileall、Wheel fresh install、`sddgov validate`、
  doctor／CI Local Green 與 DEP strict Proof 全綠。

## 真實停止點

Production cgroup v2／PID containment、runtime FD execution chain、service account、
systemd socket/unit、`/etc` bootstrap、`/var/lib` state、Owner approver identity、真實
credential 與網路規則都尚未配置。離線 Proof 完成後只能宣稱 rehearsal Runner-ready，
不得宣稱 production、Live 或部署完成。

## 回滾

移除 trusted Runner module／CLI／schemas／tests／docs／Work Package／DEP，保留 v1.2
Hard Gates 與 AF25 offline-only capsule。無資料庫或正式資料遷移。
