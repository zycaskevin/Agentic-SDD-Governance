# Synthetic Monorepo Rollback Benchmark

This benchmark measures the current Rollback v3 exact-tree static proof against synthetic repositories with many unchanged files and one changed implementation file.

Run from the source environment:

```bash
PYTHONPATH=src python scripts/benchmark_monorepo_rollback.py \
  --file-counts 1000,10000,50000 \
  --repeats 3 \
  --output benchmarks/monorepo-rollback/latest-result.json
```

The predeclared latency threshold is the verifier-owned constant: p95 greater than 5 seconds. The CLI intentionally has no threshold override. Crossing it means profile and investigate the exact-tree implementation; it does not authorize replacing Base-tree equality with an affected-path-only assertion. An incorrect proof result is a separate blocking correctness failure, never an optimization signal.

Fixture setup uses a separate bounded timeout that scales with the requested file count (180 seconds minimum, then 15 seconds per 1,000 files when larger). This prevents the default 50,000-file case from being reported as a verifier regression merely because repository construction exceeded a small-fixture timeout; measured verifier latency and its fixed threshold remain unchanged.

The output is a local synthetic latency record, not a universal production capacity or project-superiority claim. Filesystem, Git version, cache state, file size, tree shape, and hardware materially affect results.
