from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(".sddgov/ci-cost-guard.json")
WORKFLOW_SUFFIXES = (".yml", ".yaml")
FULL_MATRIX_VALUES = {"manual", "ready_for_review", "manual_or_ready_for_review", "release"}


def _read_contract(root: Path) -> dict[str, Any]:
    path = root / CONTRACT_PATH
    if not path.is_file():
        raise FileNotFoundError(f"{CONTRACT_PATH}; copy templates/CI_COST_GUARD.json and customize it")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {CONTRACT_PATH}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{CONTRACT_PATH} must contain a JSON object")
    return value


def _validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("schema_version") != "1.0":
        errors.append("CI Cost Guard schema_version must be 1.0")
    if contract.get("profile") not in {"solo-fast", "team-standard", "regulated"}:
        errors.append("CI Cost Guard profile is invalid")

    local = contract.get("local_green")
    if not isinstance(local, dict):
        errors.append("local_green must be an object")
    else:
        environment = local.get("environment", {})
        if not isinstance(environment, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in environment.items()
        ):
            errors.append("local_green.environment must map strings to strings")
        commands = local.get("commands")
        if not isinstance(commands, list) or not commands:
            errors.append("local_green.commands must be a non-empty array")
        elif not all(
            isinstance(command, list)
            and command
            and all(isinstance(argument, str) and argument for argument in command)
            for command in commands
        ):
            errors.append("each local_green command must be a non-empty string array")

    hosted = contract.get("hosted")
    if not isinstance(hosted, dict):
        errors.append("hosted must be an object")
    else:
        for key, minimum in (
            ("max_runs_per_work_package", 1),
            ("max_reruns_per_revision", 0),
            ("expected_minutes", 1),
        ):
            value = hosted.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                errors.append(f"hosted.{key} must be an integer >= {minimum}")
        if hosted.get("full_matrix") not in FULL_MATRIX_VALUES:
            errors.append("hosted.full_matrix is invalid")

    controls = contract.get("workflow_controls")
    required_controls = (
        "require_concurrency",
        "cancel_in_progress",
        "require_job_timeouts",
        "require_read_only_permissions",
        "skip_draft_pull_requests",
    )
    if not isinstance(controls, dict):
        errors.append("workflow_controls must be an object")
    else:
        for key in required_controls:
            if not isinstance(controls.get(key), bool):
                errors.append(f"workflow_controls.{key} must be boolean")
        exemptions = controls.get("exempt_workflows", [])
        if not isinstance(exemptions, list) or not all(isinstance(item, str) for item in exemptions):
            errors.append("workflow_controls.exempt_workflows must be a string array")
    return errors


def _workflow_paths(root: Path) -> list[Path]:
    workflow_root = root / ".github" / "workflows"
    if not workflow_root.is_dir():
        return []
    return sorted(
        path for path in workflow_root.iterdir()
        if path.is_file() and path.suffix.lower() in WORKFLOW_SUFFIXES
    )


def _job_blocks(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    try:
        jobs_index = next(index for index, line in enumerate(lines) if line.strip() == "jobs:" and not line.startswith(" "))
    except StopIteration:
        return []
    starts: list[tuple[int, str]] = []
    for index in range(jobs_index + 1, len(lines)):
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", lines[index])
        if match:
            starts.append((index, match.group(1)))
    blocks: list[tuple[str, str]] = []
    for position, (start, name) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        blocks.append((name, "\n".join(lines[start:end])))
    return blocks


def _automatic(text: str) -> bool:
    return bool(re.search(r"(?m)^  (pull_request|push|schedule):", text))


def _pull_request(text: str) -> bool:
    return bool(re.search(r"(?m)^  pull_request:", text))


def _pull_request_has_ready_for_review(text: str) -> bool:
    match = re.search(
        r"(?ms)^  pull_request:\s*\n(?P<body>(?:^    .*\n?)*)",
        text,
    )
    return bool(match and "ready_for_review" in match.group("body"))


def _inspect_workflow(path: Path, controls: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    jobs = [(name, block) for name, block in _job_blocks(text) if "runs-on:" in block]
    automatic = _automatic(text)
    errors: list[str] = []
    if controls.get("require_read_only_permissions") and "runs-on:" in text:
        if not re.search(r"(?ms)^permissions:\s*\n(?:^[ \t].*\n)*?^  contents:\s*read\s*$", text):
            errors.append(f"{path.name}: default permissions must include contents: read")
    if automatic and controls.get("require_concurrency") and not re.search(r"(?m)^concurrency:", text):
        errors.append(f"{path.name}: automatic workflow requires concurrency")
    if automatic and controls.get("cancel_in_progress") and not re.search(
        r"(?m)^  cancel-in-progress:\s*true\s*$", text
    ):
        errors.append(f"{path.name}: automatic workflow must cancel stale runs")
    if _pull_request(text) and controls.get("skip_draft_pull_requests"):
        if not _pull_request_has_ready_for_review(text):
            errors.append(
                f"{path.name}: pull_request types must include ready_for_review"
            )
        for name, block in jobs:
            if "github.event.pull_request.draft == false" not in block:
                errors.append(
                    f"{path.name}: pull-request job {name} must skip Draft PR runners"
                )
    if controls.get("require_job_timeouts"):
        for name, block in jobs:
            if "timeout-minutes:" not in block:
                errors.append(f"{path.name}: hosted job {name} requires timeout-minutes")
    return errors, {
        "workflow": path.name,
        "automatic": automatic,
        "hosted_jobs": [name for name, _ in jobs],
    }


def verify_guard(root: Path) -> dict[str, Any]:
    root = root.resolve()
    contract = _read_contract(root)
    errors = _validate_contract(contract)
    reports: list[dict[str, Any]] = []
    controls = contract.get("workflow_controls", {})
    exemptions = set(controls.get("exempt_workflows", [])) if isinstance(controls, dict) else set()
    paths = _workflow_paths(root)
    if not paths:
        errors.append("no GitHub Actions workflows found")
    for path in paths:
        if path.name in exemptions:
            reports.append({"workflow": path.name, "exempt": True})
            continue
        workflow_errors, report = _inspect_workflow(path, controls)
        errors.extend(workflow_errors)
        reports.append(report)
    return {
        "ok": not errors,
        "project": str(root),
        "contract": str(CONTRACT_PATH),
        "hosted_budget": contract.get("hosted", {}),
        "workflows": reports,
        "errors": errors,
    }


def run_local_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    report = verify_guard(root)
    if not report["ok"]:
        raise ValueError("CI Cost Guard verification failed: " + "; ".join(report["errors"]))
    contract = _read_contract(root)
    local = contract["local_green"]
    environment = os.environ.copy()
    environment.update(local.get("environment", {}))
    results: list[dict[str, Any]] = []
    for command in local["commands"]:
        started = time.monotonic()
        completed = subprocess.run(command, cwd=root, env=environment, check=False)
        result = {
            "command": command,
            "returncode": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        results.append(result)
        if completed.returncode != 0:
            raise ValueError(f"local Green Gate failed: {command[0]} exited {completed.returncode}")
    return {"ok": True, "project": str(root), "commands": results}
