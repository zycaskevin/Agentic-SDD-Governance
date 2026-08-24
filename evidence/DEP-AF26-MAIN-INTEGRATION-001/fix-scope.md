# 修正範圍

## Smallest sufficient change

將 AF26 approval envelope／consume route 遷移到最新 exact operation payload contract；
依 `AF26-SYNTHETIC-CONTROL-PLANE-L2-001`，只在 tests 注入明確 synthetic runtime context、
control-plane loader 與 nonce broker double，並新增 no-double fail-closed guard。正式實作仍
依賴獨立 control plane且 production hard-deny。同步 refresh managed install 與舊 DEP provenance。

## Files or components in scope

- `src/sddgov/trusted_runner.py` 與 `tests/test_trusted_runner.py`。
- canonical／packaged Trusted Runner request schema。
- `.agentic-sdd-governance` managed manifest 與三個 installed schema。
- 兩個既有 AF26 DEP metadata、本整合 DEP、SDD／Work Package 驗證紀錄。

## Explicit non-scope

不加入本機 nonce fallback、不建立假 production broker、不讀真實 credential、不使用網路、
不執行 Hermes／provider inference、Promotion、Gate Enforce 或 deployment；不降低最新 main
的 L3 operation payload、runtime context 或 broker acceptance criteria。

## Blast radius

影響 AF26 approval wire shape 與 rehearsal harness；既有 production hard-deny、sealed bundle、
source/profile binding、child cleanup、signed safe result 與其他治理模組保持不變。
