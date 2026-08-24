# 驗證

## Green command與結果

- Red四個 method共6 failures；相同四個 method修復後全綠，另加 descriptor-close回歸全綠。
- `env PYTHONPATH=src python3 -m unittest -v tests.test_trusted_runner
  tests.test_redaction tests.test_repository_contract`：45 tests，通過。
- `.venv/bin/sddgov ci verify .`：通過；hosted budget仍為每 Work Package一次，未觸發遠端。
- `.venv/bin/sddgov ci local-gate .`：256 tests與validate全綠。
- Doctor：69 managed files，0 error，0 warning。
- Fresh Wheel SHA-256：`b440c22d0b073ce533a3108385df806c87436f268507db61f3f58e9f2cfb918d`；
  isolated import、schema／redaction behavior與fresh install通過。

## Before／After

Before：stderr open／pipe write failure留下 parent FD；reason含Python類別；124000 ms被schema拒絕；
setup failure留下 patch；shareable Red log含home path與trailing whitespace。After：early failures
關閉所有已取得FD，close失敗如實回報false，failure result schema-valid，duration observation可表達
termination cleanup，test fixture可回復，受影響artifact已 deterministic重建。

## 尚存限制

- Exact-head post-fix independent protected-file review與受信簽章尚未執行。
- PR #53既有 hosted run已用完且因舊 base SHA fail closed；本次未推送、未觸發 replacement run。
- Production root-owned context、independent nonce broker、dedicated UID、cgroup v2與FD-bound runtime
  chain仍未實作，production繼續 hard-deny；本 Proof不是真實 L3全鏈路。
