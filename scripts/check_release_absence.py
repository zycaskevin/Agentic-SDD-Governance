#!/usr/bin/env python3
"""Block before approval when any release target already has this version."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

if __package__:
    from .release_validation import bounded_token, repository_slug
else:  # pragma: no cover - direct release workflow execution
    from release_validation import bounded_token, repository_slug

PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$")
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z](?:[0-9A-Za-z._+-]{0,126}[0-9A-Za-z])?$")
MAX_RESPONSE_BYTES = 1_048_576


def _get_optional_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            exc.close()
            return None
        exc.close()
        raise
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("release target response exceeds the bounded size")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("release target returned a non-object response")
    return value


def check_release_absence(
    repository: str,
    package: str,
    version: str,
    tag: str,
    github_token: str,
) -> None:
    repository = repository_slug(repository)
    if PACKAGE_PATTERN.fullmatch(package or "") is None:
        raise ValueError("package must use a bounded registry name")
    if VERSION_PATTERN.fullmatch(version or "") is None or tag != f"v{version}":
        raise ValueError("version and tag must form one exact bounded release")
    github_token = bounded_token(github_token)
    if github_token is None:
        raise ValueError("GitHub token is required")
    encoded_repository = urllib.parse.quote(repository, safe="/")
    encoded_package = urllib.parse.quote(package, safe="")
    encoded_version = urllib.parse.quote(version, safe="")
    encoded_tag = urllib.parse.quote(tag, safe="")
    targets = {
        "TestPyPI": _get_optional_json(
            f"https://test.pypi.org/pypi/{encoded_package}/{encoded_version}/json"
        ),
        "GitHub Release": _get_optional_json(
            f"https://api.github.com/repos/{encoded_repository}/releases/tags/{encoded_tag}",
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        ),
        "PyPI": _get_optional_json(
            f"https://pypi.org/pypi/{encoded_package}/{encoded_version}/json"
        ),
    }
    present = [name for name, result in targets.items() if result is not None]
    if present:
        raise ValueError(
            "release transaction already started or completed at "
            + ", ".join(present)
            + "; do not request another approval; use bounded recovery or a new version"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--package", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not args.repository or not token:
        print("release absence preflight failed: repository and GitHub token are required")
        return 1
    try:
        check_release_absence(
            args.repository,
            args.package,
            args.version,
            args.tag,
            token,
        )
    except (OSError, ValueError) as exc:
        print(f"release absence preflight failed: {exc}")
        return 1
    print("release absence preflight passed: all three release targets are empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
