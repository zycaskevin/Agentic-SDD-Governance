# Verification

## Green command and result

`PYTHONPATH=src /private/tmp/sdg-exp8-test-venv/bin/python -m pytest tests -q` passed 185 tests on Python 3.14.3 with one sandbox-only AF_UNIX skip; the real macOS AF_UNIX positive test then passed outside the socket-restricted sandbox. A fresh Python 3.11.14 environment using the hash lock passed all 185 tests without a skip. `sddgov validate`, `ci verify`, Local Green Gate, and strict full/portable verification of both experimental.8 DEPs passed.

## Before/after evidence

Before: the independent review artifact records P0/P1 bypasses at exact candidate `b323b83`. After: each bounded probe is now a permanent test that fails closed, while ordinary workflows stay Green. Fresh wheel installation at `/private/tmp/sdg-exp8-r2-final-wheel-ONeNA1` passed Codex and Hermes setup/doctor with 63 managed files each, plus the offline synthetic Muse pilot with `network_used=false` and `real_data_used=false`. The rebuilt wheel SHA-256 is `e2c44e6fc13fa670b82d914eee371008320620e8615ebf306008c9bfc1183d5e`; the rebuilt sdist SHA-256 is `5450775778f9eadd64816dba31f35256a6c57b073f9e6683727bfec7c79d165e`.

## Remaining limitations

Local Green is not independent approval. Fresh Reviewer P0=0/P1=0, exact Merge receipt, Draft hosted-check behavior, and downloaded Release-asset verification remain separate gates. No release is authorized by this DEP.
