# 驗證

## Green command and result

- `unittest discover -s tests -q`：113 passed。
- AF26＋repository contract：26 passed。
- Ruff：All checks passed；compileall 與 `sddgov validate` 成功。
- Wheel `agentic_sdd_governance-0.2.0.dev6` 建置成功；fresh target import 明確來自
  唯一 `/tmp/af26-wheel-final-*` install，packaged request Schema 含完整 profile
  documents，Trusted Runner 可匯入。
- fresh project setup／doctor：62 managed files，0 errors／0 warnings。

## Before/after evidence

Before：`sddgov.trusted_runner` import 不存在。After：synthetic exact operation 完成
source／profiles 重算 -> approval -> secret pipe -> child -> cleanup，signed result
驗證通過；replay／drift／attack paths 均在 credential 前或 fail-closed cleanup 後停止。

## Remaining limitations

Production 目前固定 `production_cgroup_containment_required`；cgroup v2 descendant
containment、FD-bound runtime chain、service UID、systemd socket／unit、`/etc` bootstrap、
`/var/lib` state、Owner production identity、真實 credential、Hermes／Provider network、
發布與部署未配置或執行。
