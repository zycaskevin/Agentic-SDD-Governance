from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError


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


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _workflow_events(document: dict[str, Any]) -> Any:
    # PyYAML 1.1 resolves the plain key `on` as boolean True.
    return document.get("on", document.get(True))


def _event_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {value: None}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return {item: None for item in value}
    if isinstance(value, dict):
        return value
    return {}


def _permission_errors(value: Any, label: str, *, require_contents: bool) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} permissions must be a mapping"]
    errors = []
    for key, permission in value.items():
        if not isinstance(key, str) or permission not in {"read", "none"}:
            errors.append(f"{label} permissions must not grant write access")
    if require_contents and value.get("contents") != "read":
        errors.append(f"{label} permissions must include contents: read")
    return errors


def _inspect_workflow(path: Path, controls: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, yaml.YAMLError) as exc:
        return [f"{path.name}: workflow YAML is invalid: {exc}"], {
            "workflow": path.name,
            "automatic": False,
            "hosted_jobs": [],
        }
    if not isinstance(document, dict):
        return [f"{path.name}: workflow must be a YAML mapping"], {
            "workflow": path.name,
            "automatic": False,
            "hosted_jobs": [],
        }
    events = _event_mapping(_workflow_events(document))
    automatic = bool(
        set(events) & {"pull_request", "pull_request_target", "push", "schedule"}
    )
    jobs_value = document.get("jobs")
    if not isinstance(jobs_value, dict):
        jobs_value = {}
        errors.append(f"{path.name}: jobs must be a mapping")
    jobs = {
        name: job
        for name, job in jobs_value.items()
        if isinstance(name, str) and isinstance(job, dict) and "runs-on" in job
    }
    if controls.get("require_read_only_permissions") and jobs:
        errors.extend(
            f"{path.name}: {error}"
            for error in _permission_errors(
                document.get("permissions"), "default", require_contents=True
            )
        )
        for name, job in jobs.items():
            if "permissions" in job:
                errors.extend(
                    f"{path.name}: {error}"
                    for error in _permission_errors(
                        job["permissions"], f"job {name}", require_contents=False
                    )
                )
    concurrency = document.get("concurrency")
    if automatic and controls.get("require_concurrency") and not isinstance(
        concurrency, dict
    ):
        errors.append(f"{path.name}: automatic workflow requires concurrency")
    if automatic and controls.get("cancel_in_progress") and (
        not isinstance(concurrency, dict)
        or concurrency.get("cancel-in-progress") is not True
    ):
        errors.append(f"{path.name}: automatic workflow must cancel stale runs")
    pull_request_events = [
        events[name]
        for name in ("pull_request", "pull_request_target")
        if name in events
    ]
    if pull_request_events and controls.get("skip_draft_pull_requests"):
        types: set[str] = set()
        for config in pull_request_events:
            if isinstance(config, dict) and isinstance(config.get("types"), list):
                types.update(
                    item for item in config["types"] if isinstance(item, str)
                )
        for required in ("ready_for_review", "converted_to_draft"):
            if required not in types:
                errors.append(
                    f"{path.name}: pull_request types must include {required}"
                )
        for name, job in jobs.items():
            condition = job.get("if")
            if not isinstance(condition, str) or (
                "github.event.pull_request.draft == false" not in condition
            ):
                errors.append(
                    f"{path.name}: pull-request job {name} must skip Draft PR runners"
                )
    if controls.get("require_job_timeouts"):
        for name, job in jobs.items():
            timeout = job.get("timeout-minutes")
            if (
                not isinstance(timeout, int)
                or isinstance(timeout, bool)
                or not 1 <= timeout <= 360
            ):
                errors.append(
                    f"{path.name}: hosted job {name} requires timeout-minutes between 1 and 360"
                )
    return errors, {
        "workflow": path.name,
        "automatic": automatic,
        "hosted_jobs": sorted(jobs),
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
