#!/usr/bin/env python3
"""Measure the existing exact-tree rollback proof on synthetic monorepos."""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from sddgov.merge_gate import rollback_ref_is_cleanly_revertible


DEFAULT_THRESHOLD_SECONDS = 5.0
DEFAULT_SETUP_TIMEOUT_SECONDS = 180
SETUP_SECONDS_PER_1000_FILES = 15
BENCHMARK_NOTE = (
    "This synthetic local benchmark measures verifier latency only. "
    "It is not a superiority, production capacity, or universal monorepo claim."
)


def setup_timeout_seconds(file_count: int) -> int:
    """Scale fixture setup time without changing the verifier latency threshold."""
    if file_count < 1:
        raise ValueError("file count must be positive")
    return max(
        DEFAULT_SETUP_TIMEOUT_SECONDS,
        math.ceil(file_count / 1000) * SETUP_SECONDS_PER_1000_FILES,
    )


def _git(root: Path, *arguments: str, timeout: int = DEFAULT_SETUP_TIMEOUT_SECONDS) -> str:
    completed = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed ({completed.returncode}): {completed.stderr}"
        )
    return completed.stdout.strip()


def _percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = math.ceil(len(ordered) * 0.95) - 1
    return ordered[min(max(index, 0), len(ordered) - 1)]


def _environment() -> dict[str, str]:
    try:
        git_version = subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        git_version = f"unavailable ({type(exc).__name__})"
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "git": git_version,
    }


def _case(file_count: int, repeats: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sddgov-monorepo-bench-") as temporary:
        root = Path(temporary)
        setup_timeout = setup_timeout_seconds(file_count)
        started = time.perf_counter()
        _git(root, "init", "--quiet")
        _git(root, "config", "user.email", "benchmark@example.invalid")
        _git(root, "config", "user.name", "Synthetic Benchmark")
        for index in range(file_count):
            package = root / "packages" / f"p{index // 1000:04d}"
            package.mkdir(parents=True, exist_ok=True)
            (package / f"file-{index:07d}.txt").write_text(
                f"synthetic baseline {index}\n", encoding="utf-8"
            )
        _git(root, "add", "packages", timeout=setup_timeout)
        _git(
            root,
            "commit",
            "--quiet",
            "-m",
            "synthetic baseline",
            timeout=setup_timeout,
        )
        base_sha = _git(root, "rev-parse", "HEAD")

        changed = root / "packages/p0000/file-0000000.txt"
        changed.write_text("synthetic implementation\n", encoding="utf-8")
        _git(root, "add", changed.relative_to(root).as_posix())
        _git(root, "commit", "--quiet", "-m", "atomic implementation")
        rollback_ref = _git(root, "rev-parse", "HEAD")

        evidence = root / "evidence/DEP-MONOREPO/rollback.md"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("synthetic audit-only descendant\n", encoding="utf-8")
        _git(root, "add", evidence.relative_to(root).as_posix())
        _git(root, "commit", "--quiet", "-m", "bind synthetic evidence")
        reviewed_head_sha = _git(root, "rev-parse", "HEAD")
        setup_seconds = time.perf_counter() - started

        samples: list[float] = []
        results: list[bool] = []
        for _ in range(repeats):
            sample_started = time.perf_counter()
            results.append(
                rollback_ref_is_cleanly_revertible(
                    root,
                    rollback_ref,
                    base_sha=base_sha,
                    reviewed_head_sha=reviewed_head_sha,
                )
            )
            samples.append(time.perf_counter() - sample_started)
        return {
            "file_count": file_count,
            "changed_file_count": 1,
            "repeats": repeats,
            "all_proofs_passed": all(results),
            "setup_seconds": round(setup_seconds, 6),
            "setup_timeout_seconds": setup_timeout,
            "samples_seconds": [round(value, 6) for value in samples],
            "median_seconds": round(statistics.median(samples), 6),
            "p95_seconds": round(_percentile_95(samples), 6),
        }


def run_benchmark(
    file_counts: list[int],
    repeats: int,
) -> dict[str, Any]:
    if not file_counts or any(value < 1 for value in file_counts):
        raise ValueError("file counts must be positive")
    if repeats < 1:
        raise ValueError("repeats must be positive")
    cases = [_case(value, repeats) for value in file_counts]
    proof_failure = any(not case["all_proofs_passed"] for case in cases)
    latency_regression = not proof_failure and any(
        case["p95_seconds"] > DEFAULT_THRESHOLD_SECONDS for case in cases
    )
    state = (
        "proof_failure"
        if proof_failure
        else "latency_regression"
        if latency_regression
        else "retain_full_tree"
    )
    return {
        "schema_version": "1.0",
        "benchmark": "exact-tree-rollback-monorepo",
        "environment": _environment(),
        "threshold_seconds_p95": DEFAULT_THRESHOLD_SECONDS,
        "cases": cases,
        "decision": {
            "state": state,
            "blocking": state != "retain_full_tree",
            "optimize_required": latency_regression,
            "action": (
                "investigate rollback-proof correctness without weakening exact Base-tree equality"
                if proof_failure
                else
                "investigate without weakening exact Base-tree equality"
                if latency_regression
                else "retain full-tree proof; no affected-path optimization"
            ),
        },
        "claim_allowed": False,
        "note": BENCHMARK_NOTE,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file-counts",
        default="1000,10000,50000",
        help="Comma-separated positive synthetic repository file counts",
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        counts = [
            int(value) for value in args.file_counts.split(",") if value.strip()
        ]
    except ValueError as exc:
        parser.error(f"--file-counts must contain integers: {exc}")
    try:
        result = run_benchmark(counts, args.repeats)
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        result = {
            "schema_version": "1.0",
            "benchmark": "exact-tree-rollback-monorepo",
            "environment": _environment(),
            "threshold_seconds_p95": DEFAULT_THRESHOLD_SECONDS,
            "cases": [],
            "decision": {
                "state": "benchmark_error",
                "blocking": True,
                "optimize_required": False,
                "action": "repair the benchmark run before making a latency decision",
            },
            "claim_allowed": False,
            "note": BENCHMARK_NOTE,
            "error": f"benchmark execution failed ({type(exc).__name__})",
        }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["decision"]["state"] == "retain_full_tree" else 1


if __name__ == "__main__":
    raise SystemExit(main())
