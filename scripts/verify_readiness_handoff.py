#!/usr/bin/env python3
"""Bind publication to one successful release-readiness workflow run."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

if __package__:
    from .release_validation import (
        MAX_EVENT_BYTES,
        MAX_HANDOFF_RECORD_BYTES,
        MAX_REF_CHARS,
        MAX_WORKFLOW_NAME_CHARS,
        MAX_WORKFLOW_PATH_CHARS,
        bounded_path,
        bounded_text,
        load_bounded_object,
        positive_github_integer,
        repository_slug,
    )
else:  # pragma: no cover - direct release workflow execution
    from release_validation import (
        MAX_EVENT_BYTES,
        MAX_HANDOFF_RECORD_BYTES,
        MAX_REF_CHARS,
        MAX_WORKFLOW_NAME_CHARS,
        MAX_WORKFLOW_PATH_CHARS,
        bounded_path,
        bounded_text,
        load_bounded_object,
        positive_github_integer,
        repository_slug,
    )

SHA_PATTERN = re.compile(r"[a-f0-9]{40}")
TAG_PATTERN = re.compile(r"v[0-9A-Za-z][0-9A-Za-z._-]*")


def _positive_integer(value: Any, label: str) -> int:
    return positive_github_integer(value, label)


def validate_workflow_run(
    event: dict[str, Any],
    *,
    expected_repository: str,
    expected_run_id: int,
    expected_sha: str,
    expected_tag: str,
    expected_workflow_name: str,
    expected_workflow_path: str,
    expected_trusted_verifier_sha: str,
) -> dict[str, Any]:
    expected_repository = repository_slug(expected_repository, "expected repository")
    if SHA_PATTERN.fullmatch(expected_sha) is None:
        raise ValueError("expected SHA must be a full lowercase Git commit ID")
    if SHA_PATTERN.fullmatch(expected_trusted_verifier_sha) is None:
        raise ValueError(
            "expected trusted verifier SHA must be a full lowercase Git commit ID"
        )
    expected_tag = bounded_text(
        expected_tag,
        "expected release tag",
        MAX_REF_CHARS,
        pattern=TAG_PATTERN,
    )
    expected_workflow_name = bounded_text(
        expected_workflow_name,
        "expected workflow name",
        MAX_WORKFLOW_NAME_CHARS,
    )
    expected_workflow_path = bounded_text(
        expected_workflow_path,
        "expected workflow path",
        MAX_WORKFLOW_PATH_CHARS,
    )
    if (
        not expected_workflow_path.startswith(".github/workflows/")
        or ".." in Path(expected_workflow_path).parts
        or "\\" in expected_workflow_path
        or not expected_workflow_path.endswith((".yml", ".yaml"))
    ):
        raise ValueError("expected workflow path must be repository-relative")
    _positive_integer(expected_run_id, "expected run ID")

    workflow_run = event.get("workflow_run")
    repository = event.get("repository")
    if not isinstance(workflow_run, dict) or not isinstance(repository, dict):
        raise ValueError("GitHub workflow_run event fields are unavailable")
    if event.get("action") != "completed":
        raise ValueError("workflow_run event action must be completed")
    if repository.get("full_name") != expected_repository:
        raise ValueError("event repository does not match the expected repository")
    run_repository = workflow_run.get("repository")
    if (
        not isinstance(run_repository, dict)
        or run_repository.get("full_name") != expected_repository
    ):
        raise ValueError("readiness run repository does not match")
    if workflow_run.get("id") != expected_run_id:
        raise ValueError("readiness run ID does not match")
    if workflow_run.get("name") != expected_workflow_name:
        raise ValueError("readiness workflow name does not match")
    if workflow_run.get("event") != "workflow_dispatch":
        raise ValueError("readiness run must be explicitly machine-dispatched")
    if workflow_run.get("status") != "completed":
        raise ValueError("readiness run is not completed")
    if workflow_run.get("conclusion") != "success":
        raise ValueError("readiness run did not succeed")
    if workflow_run.get("head_sha") != expected_sha:
        raise ValueError("readiness run SHA does not match")
    path = workflow_run.get("path")
    if not isinstance(path, str):
        raise ValueError("readiness workflow path is unavailable")
    allowed_paths = {
        expected_workflow_path,
        f"{expected_workflow_path}@{expected_tag}",
        f"{expected_workflow_path}@refs/tags/{expected_tag}",
    }
    if path not in allowed_paths:
        raise ValueError("readiness workflow path or tag binding does not match")

    run_attempt = _positive_integer(
        workflow_run.get("run_attempt"), "readiness run attempt"
    )
    workflow_id = _positive_integer(
        workflow_run.get("workflow_id"), "readiness workflow ID"
    )
    return {
        "schema_version": "1.1",
        "repository": expected_repository,
        "readiness_run_id": expected_run_id,
        "readiness_run_attempt": run_attempt,
        "readiness_workflow_id": workflow_id,
        "readiness_workflow_name": expected_workflow_name,
        "readiness_workflow_path": expected_workflow_path,
        "release_tag": expected_tag,
        "head_sha": expected_sha,
        "trusted_verifier_sha": expected_trusted_verifier_sha,
        "artifact_name": f"distributions-{expected_sha}-{run_attempt}",
    }


def _load_object(path: Path, label: str, maximum_bytes: int) -> dict[str, Any]:
    return load_bounded_object(path, label, maximum_bytes)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--trusted-verifier-sha", required=True)
    parser.add_argument("--workflow-name", default="release-candidate")
    parser.add_argument(
        "--workflow-path",
        default=".github/workflows/release-candidate.yml",
    )
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path)
    destination.add_argument("--record", type=Path)
    args = parser.parse_args()
    try:
        event = _load_object(args.event, "workflow_run event", MAX_EVENT_BYTES)
        expected = validate_workflow_run(
            event,
            expected_repository=args.repository,
            expected_run_id=args.run_id,
            expected_sha=args.sha,
            expected_tag=args.tag,
            expected_workflow_name=args.workflow_name,
            expected_workflow_path=args.workflow_path,
            expected_trusted_verifier_sha=args.trusted_verifier_sha,
        )
        if args.record is not None:
            if _load_object(
                args.record,
                "release handoff record",
                MAX_HANDOFF_RECORD_BYTES,
            ) != expected:
                raise ValueError("release handoff record does not match the workflow run")
        else:
            assert args.output is not None
            bounded_path(args.output, "release handoff output path")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                json.dump(expected, handle, indent=2, sort_keys=True)
                handle.write("\n")
    except (OSError, ValueError) as exc:
        print(f"release handoff verification failed: {exc}")
        return 1
    print(
        "release handoff verified: "
        f"run {expected['readiness_run_id']} -> {expected['release_tag']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
