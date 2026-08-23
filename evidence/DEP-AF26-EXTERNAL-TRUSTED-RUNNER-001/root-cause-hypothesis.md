# 根因假說

## 假說

v1.2 Hard Gates 的 authority 驗證正確，但 authority 與 secret／process ownership
仍沒有 OS 隔離；同程序 caller 不能成為 trusted launch boundary。

## 支持證據

- `autonomy.py` 已能重驗 Owner-signed Ed25519 receipt 並在 decision lock 原子耗用。
- `trust.py` 能安全讀 owner-only regular JSON，但無法讓同 UID caller 失去檔案權限。
- AF25 獨立審查已否證 in-process grant、caller-provided authority 與 returned secret env。
- Repository 沒有 Runner module、socket peer verification、sealed FD 或 child cleanup owner。

## 反證

既有 Hard Gates、trust loader 與 decision state 可重用，不需要重寫 signature 或
atomic consumption；缺口集中在 OS/process boundary。

## 可否證測試

若 same-UID production、wrong peer、fake bootstrap、unsealed bundle、approval replay
或 secret-before-approval 任一情境可以進入 child launch，假說的修補被否證。

## 結論

根因由 source inspection 與 Red import check 確認；本版最小充分修補是
socket-activated rehearsal Runner 與 dedicated-UID production contract，重用既有 Hard
Gates，並在 cgroup v2 與 FD-bound runtime chain 完成前對 production hard-deny。
