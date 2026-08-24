# 修正範圍

## Smallest sufficient change

在 `_run_child()` 中以與 `trusted_runner.py` 同 package 的絕對 `_trusted_exec.py`
path 取代 `-m sddgov._trusted_exec`，保留 `-I`、secret pipe、pass_fds 與現有排序。

## Files or components in scope

- `src/sddgov/trusted_runner.py`
- `tests/test_trusted_runner.py` 的 launcher argv 回歸斷言。
- 本 DEP 與 Work Package 驗證紀錄。

## Explicit non-scope

不變更 request／result Schema、approval authority、credential protocol、production
hard-deny、CI acceptance criteria、真實 credential、network、inference 或 deployment。

## Blast radius

只影響 rehearsal child launcher 入口定位；已安裝 Wheel 與 source checkout 應得到同一
launcher 邏輯。production 仍在 bootstrap load 時 hard-deny。
