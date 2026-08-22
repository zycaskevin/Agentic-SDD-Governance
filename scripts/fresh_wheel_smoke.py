#!/usr/bin/env python3
"""Smoke-test a built wheel without importing the source checkout."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

if __package__:
    from .release_files import mask_local_paths as _mask_local_paths
    from .release_files import open_directory as _open_directory
    from .release_files import open_regular_file as _open_regular_file
    from .release_files import write_new_public_report as _write_new_public_report
else:  # pragma: no cover - exercised by direct release workflow execution
    from release_files import mask_local_paths as _mask_local_paths
    from release_files import open_directory as _open_directory
    from release_files import open_regular_file as _open_regular_file
    from release_files import write_new_public_report as _write_new_public_report


def verify_offline_bundle(bundle_root: Path, wheel: Path) -> dict[str, Any]:
    supplied_bundle_root = bundle_root.expanduser()
    try:
        opened_bundle = _open_directory(supplied_bundle_root, "bundle root")
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"bundle root must be a non-symlink directory: {supplied_bundle_root}"
        ) from exc
    with opened_bundle as bundle:
        bundle_root = bundle.path
        entries: dict[str, str] = {}
        with bundle.open_regular_file(
            "SHA256SUMS.txt", "bundle manifest"
        ) as manifest:
            manifest_lines = manifest.read_text(encoding="utf-8").splitlines()
        for line in manifest_lines:
            match = re.fullmatch(
                r"([a-f0-9]{64})  ([A-Za-z0-9][A-Za-z0-9._+/-]*)", line
            )
            if match is None:
                raise ValueError("bundle manifest contains an invalid record")
            digest, relative = match.groups()
            relative_path = Path(relative)
            if (
                relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative in entries
            ):
                raise ValueError("bundle manifest contains an unsafe or duplicate path")
            entries[relative] = digest
        actual = {
            relative.as_posix()
            for relative in bundle.regular_file_inventory()
            if relative.as_posix() != "SHA256SUMS.txt"
        }
        if set(entries) != actual:
            raise ValueError("bundle manifest does not exactly match the file inventory")
        for relative, expected in entries.items():
            with bundle.open_relative_regular_file(
                Path(relative), "bundle digest input"
            ) as source:
                if source.sha256() != expected:
                    raise ValueError(f"bundle digest mismatch: {relative}")

        with _open_regular_file(wheel, "wheel") as wheel_source:
            wheel = wheel_source.path
            bundled_wheel = f"distributions/{wheel_source.name}"
            if (
                bundled_wheel not in entries
                or wheel_source.sha256() != entries[bundled_wheel]
            ):
                raise ValueError(
                    "tested wheel does not match the inventoried release wheel"
                )
        lock = bundle_root / "requirements-governance.lock"
        if "requirements-governance.lock" not in entries:
            raise ValueError("bundle does not inventory requirements-governance.lock")
        dependency_wheels = [
            path for path in entries if path.startswith("wheelhouse/")
        ]
        if not dependency_wheels or any(
            not path.endswith(".whl") for path in dependency_wheels
        ):
            raise ValueError("bundle must inventory one or more dependency wheels")
        if any(path.count("/") != 1 for path in dependency_wheels):
            raise ValueError(
                "dependency wheels must be direct children of wheelhouse/"
            )
        return {
            "root": bundle_root,
            "lock": lock,
            "wheelhouse": bundle_root / "wheelhouse",
            "file_count": len(entries),
            "bundle_file_count": len(entries) + 1,
            "entries": entries,
            "dependency_wheels": tuple(sorted(dependency_wheels)),
            "project_wheel_entry": bundled_wheel,
        }


def _copy_verified_file(source: Path, destination: Path, expected: str) -> None:
    with _open_regular_file(source, "verified snapshot source") as opened:
        if opened.sha256() != expected:
            raise ValueError(
                "verified snapshot source changed or has the wrong digest"
            )
        opened.copy_to(destination, mode=0o600)


def _snapshot_verified_bundle(
    verified: dict[str, Any], wheel: Path, snapshot_root: Path
) -> dict[str, Any]:
    snapshot_root.mkdir(mode=0o700)
    snapshot_wheelhouse = snapshot_root / "wheelhouse"
    snapshot_distributions = snapshot_root / "distributions"
    snapshot_wheelhouse.mkdir(mode=0o700)
    snapshot_distributions.mkdir(mode=0o700)
    entries = verified["entries"]

    snapshot_lock = snapshot_root / "requirements-governance.lock"
    _copy_verified_file(
        verified["lock"], snapshot_lock, entries["requirements-governance.lock"]
    )
    for relative in verified["dependency_wheels"]:
        _copy_verified_file(
            verified["root"] / relative,
            snapshot_wheelhouse / Path(relative).name,
            entries[relative],
        )
    snapshot_wheel = snapshot_distributions / wheel.name
    _copy_verified_file(
        wheel,
        snapshot_wheel,
        entries[verified["project_wheel_entry"]],
    )
    return {
        "root": snapshot_root,
        "lock": snapshot_lock,
        "wheelhouse": snapshot_wheelhouse,
        "wheel": snapshot_wheel,
        "file_count": verified["file_count"],
        "bundle_file_count": verified["bundle_file_count"],
    }


def _run(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    parse_json: bool = False,
    timeout: int = 180,
) -> str | dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
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


def _public_error(value: str) -> str:
    """Remove host-specific temporary and home paths from shareable reports."""
    return _mask_local_paths(value)


def _installed_broker_smoke(
    venv_python: Path,
    root: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    if os.name != "posix" or sys.platform not in {"linux", "darwin"}:
        return {"status": "NOT_APPLICABLE", "platform": sys.platform}
    socket_path = root / "installed-broker.sock"
    state_path = root / "installed-broker-ledger.jsonl"
    code = (
        "import os,sys; from pathlib import Path; "
        "from sddgov.broker import NonceLedger,_serve_broker_at; "
        "socket_path=Path(sys.argv[1]); state_path=Path(sys.argv[2]); "
        "ledger=NonceLedger(state_path,expected_uid=os.geteuid(),"
        "validate_parent_chain=False); "
        "_serve_broker_at(socket_path,ledger,os.getgid(),owner_uid=os.geteuid())"
    )
    process = subprocess.Popen(
        [str(venv_python), "-c", code, str(socket_path), str(state_path)],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            if socket_path.exists():
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(1)
                        client.connect(str(socket_path))
                        client.sendall(b'{"action":"health"}\n')
                        client.shutdown(socket.SHUT_WR)
                        if client.recv(64) != b"READY\n":
                            raise RuntimeError(
                                "installed Broker returned an invalid health response"
                            )
                    process.send_signal(signal.SIGTERM)
                    if process.wait(timeout=10) != 0:
                        raise RuntimeError("installed Broker did not stop cleanly")
                    process.communicate(timeout=1)
                    if socket_path.exists():
                        raise RuntimeError(
                            "installed Broker left its socket after clean shutdown"
                        )
                    return {"status": "PASS", "platform": sys.platform}
                except (ConnectionError, socket.timeout):
                    pass
            time.sleep(0.05)
        stdout, stderr = process.communicate(timeout=5)
        raise RuntimeError(
            "installed Broker did not become healthy; "
            f"stdout={stdout!r}; stderr={stderr!r}"
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.communicate(timeout=1)
        socket_path.unlink(missing_ok=True)


def smoke(
    wheel: Path,
    expected_version: str,
    python: str,
    bundle_root: Path,
) -> dict[str, Any]:
    with _open_regular_file(wheel, "wheel") as wheel_source:
        wheel = wheel_source.path
        if wheel_source.suffix != ".whl":
            raise ValueError(f"wheel path must end in .whl: {wheel}")
    bundle = verify_offline_bundle(bundle_root, wheel)

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    for key in tuple(environment):
        if key.startswith("PIP_"):
            environment.pop(key)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    temporary_parent = "/tmp" if os.name == "posix" else None
    with tempfile.TemporaryDirectory(
        prefix="sgw-", dir=temporary_parent
    ) as temporary:
        root = Path(temporary)
        bundle = _snapshot_verified_bundle(bundle, wheel, root / "verified-inputs")
        wheel = bundle["wheel"]
        virtualenv = root / "venv"
        _run(
            [python, "-m", "venv", str(virtualenv)],
            cwd=root,
            environment=environment,
            timeout=300,
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
            timeout=300,
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
            validation = _run(
                [str(venv_python), "-m", "sddgov.cli", "validate", str(project)],
                cwd=root,
                environment=environment,
            )
            if setup.get("ok") is not True or doctor.get("ok") is not True:
                raise RuntimeError(f"{agent} setup/doctor failed")
            if doctor.get("agent") != agent:
                raise RuntimeError(f"{agent} doctor reported the wrong adapter")
            if not validation.startswith("[OK]"):
                raise RuntimeError(f"{agent} installed governance validation failed")
            doctors[agent] = {
                "ok": True,
                "validation": "PASS",
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
        broker_smoke = _installed_broker_smoke(
            venv_python,
            root,
            environment,
        )

    return {
        "ok": True,
        "verdict": "PASS",
        "wheel": wheel.name,
        "version": actual_version,
        "source_checkout_imported": False,
        "offline_bundle_verified": True,
        "bundle_file_count": bundle["bundle_file_count"],
        "bundle_payload_file_count": bundle["file_count"],
        "doctors": doctors,
        "quick_demo": {
            "verdict": quick_demo["verdict"],
            "real_data_used": quick_demo["real_data_used"],
        },
        "native_broker": broker_smoke,
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
        result = {
            "ok": False,
            "verdict": "FAIL",
            "error": _public_error(str(exc)),
        }

    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    try:
        if args.output is not None:
            _write_new_public_report(args.output, rendered)
    except (OSError, ValueError) as exc:
        result = {
            "ok": False,
            "verdict": "FAIL",
            "error": _public_error(f"cannot write smoke report: {exc}"),
        }
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
