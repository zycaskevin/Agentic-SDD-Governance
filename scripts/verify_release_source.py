#!/usr/bin/env python3
"""Refresh and verify the live release source immediately before publication."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

if __package__:
    from .release_validation import (
        MAX_REF_CHARS,
        MAX_REMOTE_CHARS,
        bounded_path,
        bounded_text,
    )
else:  # pragma: no cover - direct release workflow execution
    from release_validation import (
        MAX_REF_CHARS,
        MAX_REMOTE_CHARS,
        bounded_path,
        bounded_text,
    )

SHA_PATTERN = re.compile(r"[a-f0-9]{40}")
TAG_PATTERN = re.compile(r"v[0-9A-Za-z][0-9A-Za-z._-]*")
REMOTE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
BRANCH_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
GIT_TIMEOUT_SECONDS = 10
MAX_GIT_RESULT_CHARS = 128


def _valid_branch(value: str) -> bool:
    return bool(
        BRANCH_PATTERN.fullmatch(value)
        and ".." not in value
        and "@{" not in value
        and "//" not in value
        and not value.endswith(("/", ".", ".lock"))
    )


def verify_release_source(
    repository: Path,
    *,
    remote: str,
    default_branch: str,
    release_tag: str,
    readiness_sha: str,
    trusted_verifier_sha: str,
    runner: Callable[..., Any] = subprocess.run,
) -> None:
    repository = bounded_path(repository, "trusted repository path")
    remote = bounded_text(
        remote,
        "release remote",
        MAX_REMOTE_CHARS,
        pattern=REMOTE_PATTERN,
    )
    default_branch = bounded_text(default_branch, "default branch", MAX_REF_CHARS)
    if not _valid_branch(default_branch):
        raise ValueError("default branch is invalid")
    release_tag = bounded_text(
        release_tag,
        "release tag",
        MAX_REF_CHARS,
        pattern=TAG_PATTERN,
    )
    if SHA_PATTERN.fullmatch(readiness_sha) is None:
        raise ValueError("readiness SHA must be a full lowercase commit ID")
    if SHA_PATTERN.fullmatch(trusted_verifier_sha) is None:
        raise ValueError("trusted verifier SHA must be a full lowercase commit ID")

    prefix = ["git", "-C", str(repository)]

    def checked(*arguments: str, capture_result: bool = False) -> str:
        try:
            result = runner(
                [*prefix, *arguments],
                check=True,
                text=True,
                stdout=subprocess.PIPE if capture_result else subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=GIT_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError("release source refresh or verification failed") from exc
        if not capture_result:
            return ""
        output = result.stdout
        if not isinstance(output, str) or len(output) > MAX_GIT_RESULT_CHARS:
            raise ValueError("release source command output exceeds the bounded size")
        return output.strip()

    if checked("rev-parse", "HEAD", capture_result=True) != trusted_verifier_sha:
        raise ValueError("trusted verifier checkout changed")

    checked(
        "fetch",
        "--force",
        "--no-tags",
        remote,
        f"+refs/tags/{release_tag}:refs/tags/{release_tag}",
    )
    checked(
        "fetch",
        "--force",
        "--no-tags",
        remote,
        f"+refs/heads/{default_branch}:refs/remotes/{remote}/{default_branch}",
    )
    if checked(
        "rev-list",
        "-n",
        "1",
        f"refs/tags/{release_tag}",
        capture_result=True,
    ) != readiness_sha:
        raise ValueError("live release tag no longer resolves to the readiness SHA")
    try:
        checked(
            "merge-base",
            "--is-ancestor",
            readiness_sha,
            f"refs/remotes/{remote}/{default_branch}",
        )
    except ValueError as exc:
        raise ValueError("readiness SHA is no longer in the live default branch") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--readiness-sha", required=True)
    parser.add_argument("--trusted-verifier-sha", required=True)
    args = parser.parse_args()
    try:
        verify_release_source(
            args.repository,
            remote=args.remote,
            default_branch=args.default_branch,
            release_tag=args.tag,
            readiness_sha=args.readiness_sha,
            trusted_verifier_sha=args.trusted_verifier_sha,
        )
    except ValueError as exc:
        print(f"release source verification failed: {exc}")
        return 1
    print(
        "release source verified: "
        f"{args.tag} -> {args.readiness_sha} with verifier {args.trusted_verifier_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
