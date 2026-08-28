#!/usr/bin/env python3
"""Shared bounded-input helpers for the native release handoff."""

from __future__ import annotations

import json
import os
import re
import selectors
import subprocess
import time
from pathlib import Path
from typing import Any, Pattern


MAX_AUTHORITY_POLICY_BYTES = 64 * 1024
MAX_EVENT_BYTES = 1024 * 1024
MAX_HANDOFF_RECORD_BYTES = 64 * 1024
MAX_GIT_BLOB_BYTES = 64 * 1024
MAX_ENVIRONMENT_NAME_CHARS = 255
MAX_GITHUB_TOKEN_CHARS = 8192
MAX_REF_CHARS = 255
MAX_REMOTE_CHARS = 100
MAX_REPOSITORY_PATH_CHARS = 4096
MAX_REVIEWER_LOGIN_CHARS = 100
MAX_WORKFLOW_NAME_CHARS = 255
MAX_WORKFLOW_PATH_CHARS = 512
MAX_GITHUB_INTEGER = (1 << 63) - 1

REPOSITORY_PATTERN = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/"
    r"[A-Za-z0-9._-]{1,100}"
)


def bounded_text(
    value: Any,
    label: str,
    maximum: int,
    *,
    pattern: Pattern[str] | None = None,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or (pattern is not None and pattern.fullmatch(value) is None)
    ):
        raise ValueError(f"{label} is invalid or exceeds its bounded length")
    return value


def bounded_path(path: Path, label: str) -> Path:
    bounded_text(str(path), label, MAX_REPOSITORY_PATH_CHARS)
    return path


def bounded_token(value: str | None) -> str | None:
    if value is None:
        return None
    token = bounded_text(value, "GitHub token", MAX_GITHUB_TOKEN_CHARS)
    if any(not 33 <= ord(character) <= 126 for character in token):
        raise ValueError("GitHub token is invalid or exceeds its bounded length")
    return token


def repository_slug(value: Any, label: str = "repository") -> str:
    try:
        repository = bounded_text(value, label, 140, pattern=REPOSITORY_PATTERN)
    except ValueError as exc:
        raise ValueError(
            f"{label} must use bounded owner/name form"
        ) from exc
    owner, name = repository.split("/", 1)
    if owner in {".", ".."} or name in {".", ".."}:
        raise ValueError(f"{label} must use owner/name form")
    return repository


def positive_github_integer(value: Any, label: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
        or value > MAX_GITHUB_INTEGER
    ):
        raise ValueError(f"{label} must be a bounded positive integer")
    return value


def load_bounded_object(path: Path, label: str, maximum_bytes: int) -> dict[str, Any]:
    bounded_path(path, f"{label} path")
    try:
        if path.is_symlink():
            raise ValueError(f"{label} must not be a symbolic link")
        with path.open("rb") as handle:
            payload = handle.read(maximum_bytes + 1)
    except OSError as exc:
        raise ValueError(f"{label} is unreadable or invalid") from exc
    if len(payload) > maximum_bytes:
        raise ValueError(f"{label} exceeds the byte limit")
    try:
        value = json.loads(payload)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"{label} is unreadable or invalid") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def read_bounded_git_blob(
    repository: Path,
    object_spec: str,
    *,
    maximum_bytes: int = MAX_GIT_BLOB_BYTES,
    timeout_seconds: float = 30.0,
) -> bytes:
    """Read one Git object with hard time and byte limits."""
    bounded_path(repository, "Git repository path")
    bounded_text(object_spec, "Git object specification", 1024)
    if maximum_bytes < 1 or timeout_seconds <= 0:
        raise ValueError("Git blob limits must be positive")
    try:
        process = subprocess.Popen(
            ["git", "-C", str(repository), "show", object_spec],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise ValueError("bounded Git blob read could not start") from exc
    if process.stdout is None:  # pragma: no cover - PIPE guarantees this
        process.kill()
        process.wait()
        raise ValueError("bounded Git blob read has no output pipe")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout_seconds
    payload = bytearray()

    def stop_process() -> None:
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - killed child
            raise ValueError("bounded Git blob reader could not stop") from exc

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            if not selector.select(remaining):
                raise TimeoutError
            chunk = os.read(
                process.stdout.fileno(),
                min(8192, maximum_bytes + 1 - len(payload)),
            )
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > maximum_bytes:
                raise OverflowError
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        if process.wait(timeout=remaining) != 0:
            raise ValueError("bounded Git blob read failed")
    except TimeoutError as exc:
        stop_process()
        raise ValueError("bounded Git blob read exceeded its time limit") from exc
    except subprocess.TimeoutExpired as exc:
        stop_process()
        raise ValueError("bounded Git blob read exceeded its time limit") from exc
    except OverflowError as exc:
        stop_process()
        raise ValueError("bounded Git blob read exceeded its byte limit") from exc
    except OSError as exc:
        stop_process()
        raise ValueError("bounded Git blob read failed safely") from exc
    finally:
        selector.close()
        process.stdout.close()
    return bytes(payload)
