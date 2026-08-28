# SDG 產品憲章

狀態：AF27 mainline 候選已完成本地驗證並提交 PR #57；尚未合併、設定或發布

## 為什麼需要 SDG

SDG 的目的，是讓 Agent 能持續、可驗證、可審查、可回復而且誠實地開發，
同時不讓產品 Owner 監工一般工程工作。治理必須降低 Owner 負擔，並把真正的
風險限制在清楚邊界內。

## 產品原則

> 平常隱形，風險或現實影響升高才出現；能由 Agent 或機器驗證解決的事情，
> 永遠不要叫 Owner 來解決。

SDG 從「以授權為中心」改為「以風險與實際影響為中心」。判斷依據不是
這個步驟叫不叫 Merge，而是它是否真的造成外部、Production、破壞性、高權限、
金錢、Secret 或不可逆影響。

## 三條通道

1. **開發通道**：寫程式、測試、lint、PR、Review、修 findings 都由 Agent
   完成。Owner 操作次數是 0。SHA、Base／Head、receipt、TTY、SSH signer、
   Broker 與 DEP 都不是 Owner 介面。
2. **發布準備通道**：完整 CI、Build、整合測試、獨立審查、CodeRabbit、
   rollback 與 artifact 驗證可以很嚴格，但 Owner 操作仍是 0。PASS 只代表
   「已準備好」，不代表「已發布」。
3. **真實操作通道**：公開發布、Production deploy／migration、Secret／IAM、
   真實付款、破壞性或不可逆操作才跨越現實邊界。系統只呈現一次清楚的動作、
   目的地、影響與回復方式，必要時讓 Owner 核准一次，優先使用平台原生介面。

## Merge、Review 與強授權

Merge 預設是 L1；只有 Repo 的實際設定會讓 Merge 自動觸發 L3 現實影響時，
它才升級為 L3。獨立 Reviewer 保留，但 findings 由 Main Agent 接收、判斷並交給
Builder 修復，Owner 不再搬運訊息。

CodeRabbit 等自動 Reviewer 有實際 findings 時必須修復；僅有成功狀態但明確
跳過 review，不算審查。對同一精確 revision 自動嘗試一次後，若服務跳過或不可用，
以已簽署的獨立審查、完整 Merge Gate 與 hosted CI 作為有界替代，不無限重試，
也不把外部服務故障轉交 Owner。

## 保留的控制

測試、CI、rollback、redaction、Evidence、exact refs、hash、artifact 驗證與
獨立審查都保留，並由 Agent／機器執行。Broker、Ed25519、硬體金鑰與 audit
receipt 也保留，但不放在一般開發預設路徑；只有 regulated 或真實 L3 影響，
且確實存在不同身分、裝置或權限的信任邊界時，才啟用強授權。

Broker、Ed25519、硬體金鑰、TTY 與 audit receipt 不刪除，但只有同時存在
「真實 L3 影響」與「不同身分／裝置／權限的信任邊界」才啟用。在同一台可被
控制的裝置上複製貼上 digest，不構成有意義的強身分驗證。

Installer 成功只代表治理路由與參考資源已就位，不代表 Broker、Owner 簽章或強授權
已安裝、啟動或可用。

## 目前差距

已完成的 runtime 切片讓 team-standard 能記錄一次白話 L2 選擇，並讓無真實效果的
Merge／發布準備維持 L1、Owner 零操作；真正的 Production deploy 與公開發布則固定
升級為一個精確 L3 操作。本 Repo 現在會驗證自己的 SDG 安裝層與治理 workflow 維持
停用，同時保留其他 Repo 使用 Installer 的能力，並明確回報強授權尚未啟用。本 PR
候選已實作並驗證發布準備到真實發布之間的精確 artifact handoff，主要產品文件也已
遷移。剩餘項目是獨立審查與 Merge，以及 GitHub Environment 保護、Trusted
Publishing、精確 release tag 與 registry 發布等外部 readiness；這些外部效果皆尚未
發生，因此目前不能宣稱產品重置已合併或已發布。

機器可執行的產品基準是 `specs/sdg-product-contract.json`。
