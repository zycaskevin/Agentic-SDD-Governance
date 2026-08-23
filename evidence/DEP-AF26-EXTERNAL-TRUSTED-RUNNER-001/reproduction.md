# 重現

## 預期

`sddgov.trusted_runner` 應提供程序外 Trusted Runner contract，且 import 不會
讀取 credential、耗用 approval、啟動 process 或連網。

## 實際

v1.2 只有 L3 signed receipt 驗證／原子耗用，沒有 dedicated-UID Runner、sealed
FD handoff、secret ordering 或 child lifecycle；public module import 失敗。

## 可決定步驟

```bash
PYTHONPATH=src .venv/bin/python -m unittest -q tests.test_trusted_runner
```

結果：`ModuleNotFoundError: No module named 'sddgov.trusted_runner'`。

## 環境與前置

- Commit：`af0f89ff4335223093775888d317825747525590`。
- Branch：`codex/af26-trusted-runner`。
- Linux aarch64；Python 3.11.13。
- 只使用合成資料；無 credential／approval consumption／process／network。
