from __future__ import annotations

import json
import re
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


FORMAT_CHECKER = FormatChecker()
_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


@FORMAT_CHECKER.checks("date-time", raises=(TypeError, ValueError))
def _is_rfc3339_datetime(value: object) -> bool:
    if not isinstance(value, str) or _RFC3339_DATETIME.fullmatch(value) is None:
        return False
    normalized = value.replace("t", "T")
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    datetime.fromisoformat(normalized)
    return True


def _format_path(parts: list[object]) -> str:
    return ".".join(str(part) for part in parts) or "$"


def load_schema(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON Schema must be an object: {path.name}")
    return data


def bundled_schema(name: str) -> dict[str, Any]:
    resource = resources.files("sddgov").joinpath("resources/governance/schemas", name)
    data = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"bundled JSON Schema must be an object: {name}")
    return data


def check_schema(schema: dict[str, Any]) -> list[str]:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return [f"invalid JSON Schema: {exc.message}"]
    return []


def validate_instance(instance: Any, schema: dict[str, Any]) -> list[str]:
    schema_errors = check_schema(schema)
    if schema_errors:
        return schema_errors
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    return [
        f"{_format_path(list(error.absolute_path))}: {error.message}"
        for error in sorted(
            validator.iter_errors(instance),
            key=lambda item: ([str(part) for part in item.absolute_path], item.message),
        )
    ]
