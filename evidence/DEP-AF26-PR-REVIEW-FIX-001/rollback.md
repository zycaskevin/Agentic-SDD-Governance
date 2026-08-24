# Rollback

rollback_version: 3.0
target: AF26 PR review child-failure cleanup and deterministic evidence redaction fix
rollback_action: git_revert
rollback_ref: 8fc5c47bc63569da629dd5e7b1f7a053970832cb
reconcile_action: setup_agent_from_reverted_source
reconcile_agent: codex
reconcile_profile: team-standard
verify_action: doctor_and_python_module
verify_module: unittest

## Trigger

若 unified FD ownership造成正常 child無法啟動、secret ordering改變、signed result不再符合schema，
或 deterministic redaction破壞既有 clean text／portable DEP contract，執行bounded rollback。

## Reversible steps

在 reviewed Git workflow中revert `8fc5c47bc63569da629dd5e7b1f7a053970832cb`；不得回滾已整合的
latest main。Revert後從source執行 `setup-agent --force`，使installed schema／rules與source一致。

## Data compatibility

無資料庫、正式資料、credential或nonce。Result schema回復舊版時，任何 duration超過120000 ms的
未發布rehearsal envelope不得沿用；新 home-path redaction產生的Proof必須標示失效並重新產生。

## Post-rollback verification

重新執行setup-agent、Doctor、Trusted Runner／redaction／repository contract modules、完整Local Gate，
以及所有受影響DEP portable strict verification。若任何 early failure仍洩漏FD或shareable artifact
重新暴露home path，維持PR blocked。
