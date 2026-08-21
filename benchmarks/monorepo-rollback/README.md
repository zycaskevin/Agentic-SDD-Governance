# Synthetic Monorepo Rollback Benchmark

This benchmark measures the current Rollback v3 exact-tree static proof against synthetic repositories with many unchanged files and one changed implementation file.

Run from the source environment:

```bash
PYTHONPATH=src python scripts/benchmark_monorepo_rollback.py \
  --file-counts 1000,10000,50000 \
  --repeats 3 \
  --output benchmarks/monorepo-rollback/latest-result.json
```

The predeclared investigation threshold is p95 greater than 5 seconds or any incorrect proof result. Crossing it means profile and investigate the exact-tree implementation; it does not authorize replacing Base-tree equality with an affected-path-only assertion.

The output is a local synthetic latency record, not a universal production capacity or project-superiority claim. Filesystem, Git version, cache state, file size, tree shape, and hardware materially affect results.
