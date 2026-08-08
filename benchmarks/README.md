# ASG Evidence Debugging Benchmark

The benchmark compares paired runs against the same bug snapshot:

- Track A receives symptom text and a screenshot description only.
- Track B receives the same symptom plus a redacted DEP with console/runtime/Git/test evidence.

Both tracks must use the same model family, effort, repository snapshot, time budget, tool permissions, and acceptance tests. Hidden evaluation should score root-cause correctness, first valid fix, regression prevention, scope discipline, sensitive-data handling, human interruptions, and time/cost.

The included JSON fixtures are a harness smoke test. They are not empirical results and must not be used to claim that Agentic SDD Governance is better than another workflow.
