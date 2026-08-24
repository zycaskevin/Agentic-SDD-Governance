# Root Cause Hypothesis

## Hypothesis

AF26 由多個相隔 Evidence／main-integration 的非 audit commits 組成，但 Merge Gate 的
rollback contract 只接受一個可乾淨 revert、且 revert 後能把所有 Evidence／audit 以外內容
精確恢復到 trusted Base 的 atomic commit。現有 `8fc5c47...` 只包含最後一輪 review fix，
其 revert 無法移除較早的 AF26 implementation；此外 rollback Markdown 的敘述行未標為 `#`
註解，declarative parser會將它們視為非法欄位。兩項條件均使整體 postcondition fail closed。

## Supporting evidence

- Red 在 clean exact audit head穩定回傳 `rollback record is missing or incomplete`。
- `8fc5c47...` 位於 Base 與 reviewed head之間，且其後只有 Evidence commit；range 條件成立。
- `8fc5c47...` 的 inverse 只回復最後 review fix，較早的 Trusted Runner、Schema、CLI、tests
  與 docs 仍不同於 Base，違反 `_rollback_ref_is_cleanly_revertible()` 的 Base tree equality。
- `_rollback_contract()` 對未註解的說明段落回傳 `None`；parser contract要求所有非欄位敘述
  必須是 `#` comment。

## Contradicting evidence

四份 AF26 DEP、targeted tests、Local Green與 change digest均通過，表示產品 final tree與證據
本身不是本次 Red 的根因；問題限定於 Git history 中缺少單一可執行 rollback boundary。

## Falsification test

以 append-only 方式先建立一個 Evidence／audit 以外內容等於 trusted Base 的 baseline commit，
再用單一 commit 精確重放相同 final non-Evidence tree。若第二個 commit可由 verifier 判定
cleanly revertible，且完整 candidate change digest／產品 tree不變，則 hypothesis成立；否則推翻。

## Conclusion

Confirmed。根因是 rollback atomicity與 declarative comment格式不符合 verifier，不是 Runtime、
Schema、測試或 receipt驗簽錯誤。
