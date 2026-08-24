# 回歸證據

## Regression test added or strengthened

強化 exact rehearsal 對 child argv 的斷言：必須使用絕對 `_trusted_exec.py` path、
保留 `-I`，且 parent environment 不得出現 `OPENAI_API_KEY`。

## Related tests executed

- system Python targeted：13 tests，通過。
- editable venv targeted：13 tests，通過。
- full Local Gate：113 tests，通過；repository validation 通過。
- scoped Ruff、compileall、`git diff --check`：通過。
- fresh Wheel install／origin assertion／62-file doctor：通過，0 error／0 warning。
- independent read-only security review：無 Critical／Major／Medium blocker。

## Unaffected paths sampled

Autonomy、Merge Gate、Reviewer、Installer、Evidence、Redaction、CI Guard、Schema 與
repository contracts 由 full Local Gate 取樣。
