#!/usr/bin/env python3
"""Fail closed unless a GitHub release environment has exact protections."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

if __package__:
    from .release_validation import (
        MAX_AUTHORITY_POLICY_BYTES,
        MAX_ENVIRONMENT_NAME_CHARS,
        MAX_REF_CHARS,
        MAX_REVIEWER_LOGIN_CHARS,
        bounded_text,
        bounded_token,
        load_bounded_object,
        positive_github_integer,
        repository_slug,
    )
else:  # pragma: no cover - direct release workflow execution
    from release_validation import (
        MAX_AUTHORITY_POLICY_BYTES,
        MAX_ENVIRONMENT_NAME_CHARS,
        MAX_REF_CHARS,
        MAX_REVIEWER_LOGIN_CHARS,
        bounded_text,
        bounded_token,
        load_bounded_object,
        positive_github_integer,
        repository_slug,
    )

MAX_RATE_LIMIT_DELAY_SECONDS = 60.0
MAX_RESPONSE_BYTES = 1_048_576


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


def _is_rate_limit_error(error: urllib.error.HTTPError) -> bool:
    if error.code == 429:
        return True
    if error.code != 403:
        return False
    headers = error.headers or {}
    if (
        headers.get("Retry-After") is not None
        or headers.get("X-RateLimit-Reset") is not None
        or headers.get("X-RateLimit-Remaining") == "0"
    ):
        return True
    reason = str(error.reason).lower()
    try:
        body = error.read(4096).decode("utf-8", errors="replace").lower()
    except OSError:
        body = ""
    return "rate limit" in reason or "rate limit" in body


def validate_environment(
    environment: dict[str, Any],
    branch_policies: dict[str, Any],
    expected_ref: str,
    expected_ref_type: str,
    expected_reviewers: list[tuple[str, int, str]],
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
        else:
            actual_reviewers: list[tuple[str, int, str]] = []
            for row in reviewers:
                reviewer = row.get("reviewer") if isinstance(row, dict) else None
                reviewer_type = row.get("type") if isinstance(row, dict) else None
                reviewer_id = reviewer.get("id") if isinstance(reviewer, dict) else None
                reviewer_login = (
                    reviewer.get("login") if isinstance(reviewer, dict) else None
                )
                if (
                    reviewer_type not in {"User", "Team"}
                    or not isinstance(reviewer_id, int)
                    or isinstance(reviewer_id, bool)
                    or reviewer_id <= 0
                    or not isinstance(reviewer_login, str)
                    or not reviewer_login
                ):
                    errors.append("environment reviewer inventory is malformed")
                    break
                actual_reviewers.append(
                    (reviewer_type, reviewer_id, reviewer_login)
                )
            else:
                if actual_reviewers != expected_reviewers:
                    errors.append(
                        "environment reviewer identity does not match the trusted "
                        f"release authority; got {actual_reviewers!r}"
                    )
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
        if total_count != 1 or normalized != [(expected_ref, expected_ref_type)]:
            errors.append(
                "environment must allow only the exact deployment ref "
                f"{expected_ref!r} ({expected_ref_type}); got {normalized!r}"
            )
    return errors


def load_release_authority(
    path: Path, repository: str, environment_name: str
) -> list[tuple[str, int, str]]:
    value = load_bounded_object(
        path,
        "trusted release authority policy",
        MAX_AUTHORITY_POLICY_BYTES,
    )
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "repository",
        "environment",
        "reviewers",
    }:
        raise ValueError("trusted release authority policy has an invalid contract")
    if (
        value.get("schema_version") != "1.0"
        or value.get("repository") != repository
        or value.get("environment") != environment_name
    ):
        raise ValueError("trusted release authority policy does not match this operation")
    reviewers = value.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) != 1:
        raise ValueError("trusted release authority must name exactly one reviewer")
    row = reviewers[0]
    if not isinstance(row, dict) or set(row) != {"type", "id", "login"}:
        raise ValueError("trusted release authority reviewer is malformed")
    reviewer_type = row.get("type")
    reviewer_id = row.get("id")
    reviewer_login = row.get("login")
    if (
        reviewer_type not in {"User", "Team"}
        or not isinstance(reviewer_login, str)
    ):
        raise ValueError("trusted release authority reviewer is malformed")
    positive_github_integer(reviewer_id, "trusted release authority reviewer ID")
    bounded_text(
        reviewer_login,
        "trusted release authority reviewer login",
        MAX_REVIEWER_LOGIN_CHARS,
    )
    return [(reviewer_type, reviewer_id, reviewer_login)]


def _get_json(url: str, token: str | None = None) -> dict[str, Any]:
    token = bounded_token(token)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        headers=headers,
    )
    for attempt in range(3):
        delay: float | None = None
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except urllib.error.HTTPError as exc:
            rate_limited = _is_rate_limit_error(exc)
            retryable = rate_limited or 500 <= exc.code <= 599
            if rate_limited:
                delay = _rate_limit_delay(exc)
            exc.close()
            if not retryable or attempt == 2:
                raise
        except urllib.error.URLError:
            if attempt == 2:
                raise
        time.sleep(delay if delay is not None else 0.25 * (2**attempt))
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("GitHub API response exceeds the bounded size")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("GitHub API returned a non-object response")
    return value


def check(
    repository: str,
    environment_name: str,
    expected_ref: str,
    expected_ref_type: str,
    token: str | None,
    authority_policy: Path,
) -> None:
    repository = repository_slug(repository)
    environment_name = bounded_text(
        environment_name,
        "environment",
        MAX_ENVIRONMENT_NAME_CHARS,
    )
    expected_ref = bounded_text(expected_ref, "exact ref", MAX_REF_CHARS)
    token = bounded_token(token)
    if expected_ref_type not in {"branch", "tag"}:
        raise ValueError("environment, exact ref, and branch/tag ref type are required")
    expected_reviewers = load_release_authority(
        authority_policy, repository, environment_name
    )
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
    errors = validate_environment(
        environment,
        policies,
        expected_ref,
        expected_ref_type,
        expected_reviewers,
    )
    if errors:
        raise ValueError("; ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--environment", required=True)
    parser.add_argument("--expected-ref", required=True)
    parser.add_argument("--expected-ref-type", choices=("branch", "tag"), required=True)
    parser.add_argument("--authority-policy", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not args.repository:
        print("release environment preflight failed: GITHUB_REPOSITORY is required")
        return 1
    try:
        check(
            args.repository,
            args.environment,
            args.expected_ref,
            args.expected_ref_type,
            token,
            args.authority_policy,
        )
    except (OSError, ValueError, http.client.HTTPException) as exc:
        print(f"release environment preflight failed: {exc}")
        return 1
    print(
        "release environment preflight passed: "
        f"{args.environment} allows only {args.expected_ref_type} {args.expected_ref}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
