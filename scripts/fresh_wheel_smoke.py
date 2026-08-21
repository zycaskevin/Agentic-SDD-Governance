#!/usr/bin/env python3
"""Smoke-test a built wheel without importing the source checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _regular_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    metadata = path.stat(follow_symlinks=False)
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError(f"{label} must be a single-linked regular file: {path}")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_offline_bundle(bundle_root: Path, wheel: Path) -> dict[str, Any]:
    supplied_bundle_root = bundle_root.expanduser()
    metadata = supplied_bundle_root.stat(follow_symlinks=False)
    if supplied_bundle_root.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(
            f"bundle root must be a non-symlink directory: {supplied_bundle_root}"
        )
    bundle_root = supplied_bundle_root.resolve(strict=True)
    manifest = _regular_file(bundle_root / "SHA256SUMS.txt", "bundle manifest")
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9][A-Za-z0-9._+/-]*)", line)
        if match is None:
            raise ValueError("bundle manifest contains an invalid record")
        digest, relative = match.groups()
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts or relative in entries:
            raise ValueError("bundle manifest contains an unsafe or duplicate path")
        entries[relative] = digest
    actual: set[str] = set()
    for path in bundle_root.rglob("*"):
        path_metadata = path.stat(follow_symlinks=False)
        if path.is_symlink():
            raise ValueError(f"bundle must not contain symlinks: {path}")
        if stat.S_ISDIR(path_metadata.st_mode):
            continue
        if not stat.S_ISREG(path_metadata.st_mode) or path_metadata.st_nlink != 1:
            raise ValueError(f"bundle must contain only single-linked regular files: {path}")
        relative = path.relative_to(bundle_root).as_posix()
        if relative != "SHA256SUMS.txt":
            actual.add(relative)
    if set(entries) != actual:
        raise ValueError("bundle manifest does not exactly match the file inventory")
    for relative, expected in entries.items():
        if _sha256(bundle_root / relative) != expected:
            raise ValueError(f"bundle digest mismatch: {relative}")

    wheel = _regular_file(wheel, "wheel")
    bundled_wheel = f"distributions/{wheel.name}"
    if bundled_wheel not in entries or _sha256(wheel) != entries[bundled_wheel]:
        raise ValueError("tested wheel does not match the inventoried release wheel")
    lock = bundle_root / "requirements-governance.lock"
    if "requirements-governance.lock" not in entries:
        raise ValueError("bundle does not inventory requirements-governance.lock")
    dependency_wheels = [path for path in entries if path.startswith("wheelhouse/")]
    if not dependency_wheels or any(not path.endswith(".whl") for path in dependency_wheels):
        raise ValueError("bundle must inventory one or more dependency wheels")
    return {
        "root": bundle_root,
        "lock": lock,
        "wheelhouse": bundle_root / "wheelhouse",
        "file_count": len(entries),
    }


def _run(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    parse_json: bool = False,
) -> str | dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    output = completed.stdout.strip()
    if not parse_json:
        return output
    try:
        value = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command did not emit JSON: {' '.join(command)}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"command did not emit a JSON object: {' '.join(command)}")
    return value


def smoke(
    wheel: Path,
    expected_version: str,
    python: str,
    bundle_root: Path,
) -> dict[str, Any]:
    wheel = _regular_file(wheel, "wheel")
    if wheel.suffix != ".whl":
        raise ValueError(f"wheel path must end in .whl: {wheel}")
    bundle = verify_offline_bundle(bundle_root, wheel)

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    with tempfile.TemporaryDirectory(prefix="sddgov-wheel-smoke-") as temporary:
        root = Path(temporary)
        virtualenv = root / "venv"
        _run(
            [python, "-m", "venv", str(virtualenv)],
            cwd=root,
            environment=environment,
        )
        venv_python = virtualenv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(bundle["wheelhouse"]),
                "--require-hashes",
                "-r",
                str(bundle["lock"]),
            ],
            cwd=root,
            environment=environment,
        )
        _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheel),
            ],
            cwd=root,
            environment=environment,
        )

        actual_version = _run(
            [str(venv_python), "-m", "sddgov.cli", "--version"],
            cwd=root,
            environment=environment,
        )
        if actual_version != expected_version:
            raise RuntimeError(
                f"wheel version mismatch: expected {expected_version}, got {actual_version}"
            )

        doctors: dict[str, dict[str, Any]] = {}
        for agent in ("codex", "hermes"):
            project = root / f"{agent}-project"
            project.mkdir()
            setup = _run(
                [
                    str(venv_python),
                    "-m",
                    "sddgov.cli",
                    "setup-agent",
                    str(project),
                    "--agent",
                    agent,
                    "--profile",
                    "team-standard",
                ],
                cwd=root,
                environment=environment,
                parse_json=True,
            )
            doctor = _run(
                [str(venv_python), "-m", "sddgov.cli", "doctor", str(project)],
                cwd=root,
                environment=environment,
                parse_json=True,
            )
            if setup.get("ok") is not True or doctor.get("ok") is not True:
                raise RuntimeError(f"{agent} setup/doctor failed")
            if doctor.get("agent") != agent:
                raise RuntimeError(f"{agent} doctor reported the wrong adapter")
            doctors[agent] = {
                "ok": True,
                "managed_file_count": doctor.get("managed_file_count"),
            }

        quick_demo = _run(
            [str(venv_python), "-m", "sddgov.cli", "pilot", "quick"],
            cwd=root,
            environment=environment,
            parse_json=True,
        )
        if quick_demo.get("verdict") != "PASS":
            raise RuntimeError("installed-wheel quick demo did not pass")
        if quick_demo.get("real_data_used") is not False:
            raise RuntimeError("installed-wheel quick demo must not use real data")

    return {
        "ok": True,
        "verdict": "PASS",
        "wheel": wheel.name,
        "version": actual_version,
        "source_checkout_imported": False,
        "offline_bundle_verified": True,
        "bundle_file_count": bundle["file_count"],
        "doctors": doctors,
        "quick_demo": {
            "verdict": quick_demo["verdict"],
            "real_data_used": quick_demo["real_data_used"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--bundle-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        result = smoke(
            args.wheel,
            args.expected_version,
            args.python,
            args.bundle_root,
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"ok": False, "verdict": "FAIL", "error": str(exc)}

    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
