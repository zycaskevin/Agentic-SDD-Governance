from __future__ import annotations

import copy
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError


CONTRACT_PATH = Path(".sddgov/ci-cost-guard.json")
WORKFLOW_SUFFIXES = (".yml", ".yaml")
FULL_MATRIX_VALUES = {"manual", "ready_for_review", "manual_or_ready_for_review", "release"}
POST_MERGE_VERIFICATION_VALUES = {"manual_only", "automatic"}


def _read_contract(root: Path) -> dict[str, Any]:
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptors: list[int] = []
    try:
        descriptors.append(os.open(root, directory_flags))
        descriptors.append(
            os.open(".sddgov", directory_flags, dir_fd=descriptors[-1])
        )
        state_fd = descriptors[-1]
        before = os.stat(
            "ci-cost-guard.json", dir_fd=state_fd, follow_symlinks=False
        )
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
        ):
            raise ValueError(f"{CONTRACT_PATH} must be a single-linked regular file")
        descriptor = os.open(
            "ci-cost-guard.json",
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=state_fd,
        )
        descriptors.append(descriptor)
        opened = os.fstat(descriptor)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.stat(
            "ci-cost-guard.json", dir_fd=state_fd, follow_symlinks=False
        )
        identity = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
            opened.st_nlink,
        )
        if (
            not stat.S_ISREG(opened.st_mode)
            or identity
            != (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
                before.st_nlink,
            )
            or identity
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
                after.st_nlink,
            )
        ):
            raise ValueError(f"{CONTRACT_PATH} changed during read")
        state_entry = os.stat(
            ".sddgov", dir_fd=descriptors[0], follow_symlinks=False
        )
        state_opened = os.fstat(state_fd)
        if (
            stat.S_ISLNK(state_entry.st_mode)
            or not stat.S_ISDIR(state_entry.st_mode)
            or (state_entry.st_dev, state_entry.st_ino)
            != (state_opened.st_dev, state_opened.st_ino)
        ):
            raise ValueError(f"{CONTRACT_PATH} parent changed during read")
        value = json.loads(b"".join(chunks).decode("utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"{CONTRACT_PATH}; copy templates/CI_COST_GUARD.json and customize it"
        ) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"unsafe {CONTRACT_PATH}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {CONTRACT_PATH}: {exc}") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
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
        if hosted.get("post_merge_verification", "automatic") not in POST_MERGE_VERIFICATION_VALUES:
            errors.append("hosted.post_merge_verification is invalid")

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
        elif any(not item.strip() for item in exemptions):
            errors.append(
                "workflow_controls.exempt_workflows must contain non-empty strings"
            )
        elif len(set(exemptions)) != len(exemptions):
            errors.append("workflow_controls.exempt_workflows must not contain duplicates")
        permission_exceptions = controls.get("write_permission_exceptions", {})
        if not isinstance(permission_exceptions, dict):
            errors.append(
                "workflow_controls.write_permission_exceptions must be an object"
            )
        else:
            for workflow_name, job_exceptions in permission_exceptions.items():
                if not isinstance(workflow_name, str) or not workflow_name.strip():
                    errors.append(
                        "workflow_controls.write_permission_exceptions workflow names must be non-empty strings"
                    )
                    continue
                if not isinstance(job_exceptions, dict):
                    errors.append(
                        f"workflow_controls.write_permission_exceptions.{workflow_name} must be an object"
                    )
                    continue
                if not job_exceptions:
                    errors.append(
                        "workflow_controls.write_permission_exceptions."
                        f"{workflow_name} must name at least one job"
                    )
                    continue
                for job_name, permissions in job_exceptions.items():
                    if not isinstance(job_name, str) or not job_name.strip():
                        errors.append(
                            "workflow_controls.write_permission_exceptions."
                            f"{workflow_name} job names must be non-empty strings"
                        )
                        continue
                    if (
                        not isinstance(permissions, list)
                        or not permissions
                        or not all(
                            isinstance(permission, str) and permission.strip()
                            for permission in permissions
                        )
                        or len(set(permissions)) != len(permissions)
                    ):
                        errors.append(
                            "workflow_controls.write_permission_exceptions."
                            f"{workflow_name}.{job_name} must be a non-empty array of unique permission names"
                        )
            if isinstance(exemptions, list) and all(
                isinstance(item, str) for item in exemptions
            ):
                for workflow_name in sorted(
                    set(exemptions) & set(permission_exceptions)
                ):
                    errors.append(
                        "exempt workflow must not declare write permission "
                        f"exceptions: {workflow_name}"
                    )
    return errors


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


_UniqueKeyLoader.yaml_implicit_resolvers = copy.deepcopy(
    yaml.SafeLoader.yaml_implicit_resolvers
)
for first_character, resolvers in list(
    _UniqueKeyLoader.yaml_implicit_resolvers.items()
):
    _UniqueKeyLoader.yaml_implicit_resolvers[first_character] = [
        resolver
        for resolver in resolvers
        if resolver[0] != "tag:yaml.org,2002:bool"
    ]
_UniqueKeyLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping key must be a scalar value",
                key_node.start_mark,
            ) from exc
        if duplicate:
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
    return document.get("on")


def _event_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {value: None}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return {item: None for item in value}
    if isinstance(value, dict):
        return value
    return {}


def _permission_errors(
    value: Any,
    label: str,
    *,
    require_contents: bool,
    allowed_writes: set[str] | None = None,
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} permissions must be a mapping"]
    allowed = allowed_writes or set()
    errors = []
    for key, permission in value.items():
        if not isinstance(key, str) or (
            permission not in {"read", "none"}
            and not (permission == "write" and key in allowed)
        ):
            errors.append(f"{label} permissions must not grant write access")
    if require_contents and value.get("contents") != "read":
        errors.append(f"{label} permissions must include contents: read")
    for permission in sorted(allowed):
        if value.get(permission) != "write":
            errors.append(
                f"{label} write permission exception is unused: {permission}"
            )
    return errors


def _safe_workflow_documents(root: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """Read workflow files without following repository-controlled links."""
    documents: list[tuple[str, str]] = []
    errors: list[str] = []
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    try:
        descriptors.append(os.open(root, directory_flags))
        for component in (".github", "workflows"):
            try:
                child = os.open(component, directory_flags, dir_fd=descriptors[-1])
            except FileNotFoundError:
                return [], ["no GitHub Actions workflows found"]
            except OSError as exc:
                return [], [f"workflow directory is unsafe: {exc}"]
            metadata = os.fstat(child)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child)
                return [], ["workflow directory component must be a directory"]
            descriptors.append(child)
        workflows_fd = descriptors[-1]
        for name in sorted(os.listdir(workflows_fd)):
            if Path(name).suffix.lower() not in WORKFLOW_SUFFIXES:
                continue
            descriptor = -1
            try:
                before = os.stat(name, dir_fd=workflows_fd, follow_symlinks=False)
                if (
                    stat.S_ISLNK(before.st_mode)
                    or not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                ):
                    errors.append(
                        f"{name}: workflow must be a single-linked regular file"
                    )
                    continue
                descriptor = os.open(
                    name,
                    os.O_RDONLY
                    | getattr(os, "O_NONBLOCK", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=workflows_fd,
                )
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino)
                    != (before.st_dev, before.st_ino)
                ):
                    raise ValueError("workflow identity changed before read")
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                after = os.stat(name, dir_fd=workflows_fd, follow_symlinks=False)
                if (
                    not stat.S_ISREG(after.st_mode)
                    or after.st_nlink != 1
                    or (
                        after.st_dev,
                        after.st_ino,
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    )
                    != (
                        opened.st_dev,
                        opened.st_ino,
                        opened.st_size,
                        opened.st_mtime_ns,
                        opened.st_ctime_ns,
                    )
                ):
                    raise ValueError("workflow identity changed during read")
                documents.append((name, b"".join(chunks).decode("utf-8")))
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                errors.append(f"{name}: workflow file is unsafe: {exc}")
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        for index, component in enumerate((".github", "workflows")):
            current = os.stat(
                component, dir_fd=descriptors[index], follow_symlinks=False
            )
            opened = os.fstat(descriptors[index + 1])
            if (
                stat.S_ISLNK(current.st_mode)
                or not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino)
                != (opened.st_dev, opened.st_ino)
            ):
                errors.append("workflow directory changed during verification")
    except OSError as exc:
        errors.append(f"workflow filesystem boundary is unsafe: {exc}")
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    return documents, errors


def _draft_condition_is_safe(condition: Any, event_names: set[str]) -> bool:
    if not isinstance(condition, str) or len(event_names) != 1:
        return False
    expression = condition.strip()
    if expression.startswith("${{") and expression.endswith("}}"):
        expression = expression[3:-2].strip()
    compact = re.sub(r"\s+", "", expression)
    event_name = next(iter(event_names))
    accepted = {
        f"github.event_name!='{event_name}'||github.event.pull_request.draft==false",
        f'github.event_name!="{event_name}"||github.event.pull_request.draft==false',
    }
    return compact in accepted


def _valid_runner(value: Any) -> bool:
    return (isinstance(value, str) and bool(value.strip())) or (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def _inspect_workflow(
    workflow_name: str,
    source: str,
    controls: dict[str, Any],
    hosted: dict[str, Any],
    write_permission_exceptions: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        document = yaml.load(source, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        return [f"{workflow_name}: workflow YAML is invalid: {exc}"], {
            "workflow": workflow_name,
            "automatic": False,
            "hosted_jobs": [],
        }
    if not isinstance(document, dict):
        return [f"{workflow_name}: workflow must be a YAML mapping"], {
            "workflow": workflow_name,
            "automatic": False,
            "hosted_jobs": [],
        }
    events = _event_mapping(_workflow_events(document))
    automatic = bool(
        set(events) & {"pull_request", "pull_request_target", "push", "schedule"}
    )
    if hosted.get("post_merge_verification", "automatic") == "manual_only" and "push" in events:
        errors.append(
            f"{workflow_name}: manual-only post-merge verification forbids automatic push"
        )
    jobs_value = document.get("jobs")
    if not isinstance(jobs_value, dict):
        jobs_value = {}
        errors.append(f"{workflow_name}: jobs must be a mapping")
    jobs = {
        job_name: job
        for job_name, job in jobs_value.items()
        if isinstance(job_name, str) and isinstance(job, dict)
    }
    if len(jobs) != len(jobs_value):
        errors.append(
            f"{workflow_name}: every job must be a named mapping with an explicit runner"
        )
    for job_name, job in jobs.items():
        if not _valid_runner(job.get("runs-on")):
            errors.append(
                f"{workflow_name}: job {job_name} has an invalid runs-on value"
            )
    job_write_exceptions = (
        write_permission_exceptions
        if isinstance(write_permission_exceptions, dict)
        else {}
    )
    for unknown_job in sorted(set(job_write_exceptions) - set(jobs)):
        errors.append(
            f"{workflow_name}: write permission exception references unknown job {unknown_job}"
        )
    if controls.get("require_read_only_permissions") and jobs:
        errors.extend(
            f"{workflow_name}: {error}"
            for error in _permission_errors(
                document.get("permissions"), "default", require_contents=True
            )
        )
        for job_name, job in jobs.items():
            allowed_writes_value = job_write_exceptions.get(job_name, [])
            allowed_writes = (
                set(allowed_writes_value)
                if isinstance(allowed_writes_value, list)
                and all(isinstance(item, str) for item in allowed_writes_value)
                else set()
            )
            if "permissions" in job:
                errors.extend(
                    f"{workflow_name}: {error}"
                    for error in _permission_errors(
                        job["permissions"],
                        f"job {job_name}",
                        require_contents=False,
                        allowed_writes=allowed_writes,
                    )
                )
            elif allowed_writes:
                errors.append(
                    f"{workflow_name}: job {job_name} write permission exception requires an explicit permissions mapping"
                )
    concurrency = document.get("concurrency")
    if jobs and controls.get("require_concurrency") and not isinstance(
        concurrency, dict
    ):
        errors.append(f"{workflow_name}: hosted workflow requires concurrency")
    if jobs and isinstance(concurrency, dict) and (
        not isinstance(concurrency.get("group"), str)
        or not concurrency["group"].strip()
    ):
        errors.append(
            f"{workflow_name}: hosted workflow concurrency requires a non-empty group"
        )
    if automatic and controls.get("cancel_in_progress") and (
        not isinstance(concurrency, dict)
        or concurrency.get("cancel-in-progress") is not True
    ):
        errors.append(f"{workflow_name}: automatic workflow must cancel stale runs")
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
                    f"{workflow_name}: pull_request types must include {required}"
                )
        event_names = {
            event_name
            for event_name in ("pull_request", "pull_request_target")
            if event_name in events
        }
        for job_name, job in jobs.items():
            condition = job.get("if")
            if not _draft_condition_is_safe(condition, event_names):
                errors.append(
                    f"{workflow_name}: pull-request job {job_name} must skip Draft PR runners with the exact guard"
                )
    if controls.get("require_job_timeouts"):
        for job_name, job in jobs.items():
            timeout = job.get("timeout-minutes")
            if (
                not isinstance(timeout, int)
                or isinstance(timeout, bool)
                or not 1 <= timeout <= 360
            ):
                errors.append(
                    f"{workflow_name}: hosted job {job_name} requires timeout-minutes between 1 and 360"
                )
    return errors, {
        "workflow": workflow_name,
        "automatic": automatic,
        "hosted_jobs": sorted(jobs),
    }


def verify_guard(root: Path) -> dict[str, Any]:
    root = root.resolve()
    contract = _read_contract(root)
    errors = _validate_contract(contract)
    reports: list[dict[str, Any]] = []
    controls_value = contract.get("workflow_controls", {})
    hosted_value = contract.get("hosted", {})
    controls = controls_value if isinstance(controls_value, dict) else {}
    hosted = hosted_value if isinstance(hosted_value, dict) else {}
    exemptions_value = controls.get("exempt_workflows", [])
    exemptions = (
        set(exemptions_value)
        if isinstance(exemptions_value, list)
        and all(isinstance(item, str) for item in exemptions_value)
        else set()
    )
    permission_exceptions_value = controls.get("write_permission_exceptions", {})
    permission_exceptions = (
        permission_exceptions_value
        if isinstance(permission_exceptions_value, dict)
        else {}
    )
    documents, filesystem_errors = _safe_workflow_documents(root)
    errors.extend(filesystem_errors)
    if not documents and not filesystem_errors:
        errors.append("no GitHub Actions workflows found")
    workflow_names = {name for name, _source in documents}
    for missing in sorted(exemptions - workflow_names):
        errors.append("exempt workflows reference missing workflow " + missing)
    for missing in sorted(set(permission_exceptions) - workflow_names):
        errors.append(
            "write permission exceptions reference missing workflow " + missing
        )
    for name, source in documents:
        exempt = name in exemptions
        workflow_errors, report = _inspect_workflow(
            name,
            source,
            {} if exempt else controls,
            hosted,
            {} if exempt else permission_exceptions.get(name, {}),
        )
        errors.extend(workflow_errors)
        if exempt:
            report["exempt"] = True
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
