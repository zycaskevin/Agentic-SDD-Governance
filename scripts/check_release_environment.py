#!/usr/bin/env python3
"""Fail closed unless a GitHub release environment has exact protections."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9._-]+$"
)
MAX_RATE_LIMIT_DELAY_SECONDS = 60.0


def _rate_limit_delay(error: urllib.error.HTTPError) -> float:
    headers = error.headers or {}
    retry_after = headers.get("Retry-After")
    if retry_after is not None:
        try:
            return min(MAX_RATE_LIMIT_DELAY_SECONDS, max(0.0, float(retry_after)))
        except ValueError:
            pass
    reset = headers.get("X-RateLimit-Reset")
    if reset is not None:
        try:
            return min(
                MAX_RATE_LIMIT_DELAY_SECONDS,
                max(0.0, float(reset) - time.time()),
            )
        except ValueError:
            pass
    return MAX_RATE_LIMIT_DELAY_SECONDS


def validate_environment(
    environment: dict[str, Any],
    branch_policies: dict[str, Any],
    expected_tag: str,
) -> list[str]:
    errors: list[str] = []
    rules = environment.get("protection_rules")
    if not isinstance(rules, list):
        errors.append("environment protection_rules are unavailable")
        rules = []
    reviewer_rules = [
        rule
        for rule in rules
        if isinstance(rule, dict) and rule.get("type") == "required_reviewers"
    ]
    if len(reviewer_rules) != 1:
        errors.append("environment must have exactly one required_reviewers rule")
    else:
        rule = reviewer_rules[0]
        reviewers = rule.get("reviewers")
        if not isinstance(reviewers, list) or not reviewers:
            errors.append("environment must require at least one reviewer")
        if rule.get("prevent_self_review") is not True:
            errors.append("environment must prevent self-review")
    if environment.get("can_admins_bypass") is not False:
        errors.append("environment must explicitly disallow administrator bypass")

    policy = environment.get("deployment_branch_policy")
    if not isinstance(policy, dict):
        errors.append("environment deployment branch policy is unavailable")
    elif policy.get("custom_branch_policies") is not True or policy.get(
        "protected_branches"
    ) is not False:
        errors.append("environment must use custom deployment policies only")

    policies = branch_policies.get("branch_policies")
    if not isinstance(policies, list):
        errors.append("environment deployment policy inventory is unavailable")
    else:
        total_count = branch_policies.get("total_count")
        if (
            not isinstance(total_count, int)
            or isinstance(total_count, bool)
            or total_count != len(policies)
        ):
            errors.append(
                "environment API did not return the complete policy inventory"
            )
        normalized = [
            (row.get("name"), row.get("type"))
            for row in policies
            if isinstance(row, dict)
        ]
        if total_count != 1 or normalized != [(expected_tag, "tag")]:
            errors.append(
                f"environment must allow only the exact tag {expected_tag!r}; got {normalized!r}"
            )
    return errors


def _get_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    for attempt in range(3):
        delay: float | None = None
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                value = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            retryable = exc.code in (403, 429) or 500 <= exc.code <= 599
            if exc.code in (403, 429):
                delay = _rate_limit_delay(exc)
            exc.close()
            if not retryable or attempt == 2:
                raise
        except urllib.error.URLError:
            if attempt == 2:
                raise
        time.sleep(delay if delay is not None else 0.25 * (2**attempt))
    if not isinstance(value, dict):
        raise ValueError("GitHub API returned a non-object response")
    return value


def check(repository: str, environment_name: str, expected_tag: str, token: str) -> None:
    if REPOSITORY_PATTERN.fullmatch(repository) is None:
        raise ValueError("repository must use owner/name form")
    owner, name = repository.split("/", 1)
    if owner in {".", ".."} or name in {".", ".."}:
        raise ValueError("repository must use owner/name form")
    if not environment_name or not expected_tag.startswith("v"):
        raise ValueError("environment and exact v-prefixed tag are required")
    base = "https://api.github.com/repos/" + urllib.parse.quote(
        repository, safe="/"
    )
    encoded_environment = urllib.parse.quote(environment_name, safe="")
    environment = _get_json(
        f"{base}/environments/{encoded_environment}", token
    )
    policies = _get_json(
        f"{base}/environments/{encoded_environment}/deployment-branch-policies?per_page=100",
        token,
    )
    errors = validate_environment(environment, policies, expected_tag)
    if errors:
        raise ValueError("; ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--environment", required=True)
    parser.add_argument("--expected-tag", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not args.repository or not token:
        print("release environment preflight failed: GITHUB_REPOSITORY and GITHUB_TOKEN are required")
        return 1
    try:
        check(args.repository, args.environment, args.expected_tag, token)
    except (OSError, ValueError, urllib.error.HTTPError) as exc:
        print(f"release environment preflight failed: {exc}")
        return 1
    print(
        f"release environment preflight passed: {args.environment} allows only {args.expected_tag}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
