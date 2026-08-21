#!/usr/bin/env python3
"""Build a deterministic, hash-inventoried offline release bundle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path
from typing import Any

if __package__:
    from .release_files import SAFE_NAME, regular_file as _regular_file
    from .release_files import sha256_file as _sha256
else:  # pragma: no cover - exercised by direct release workflow execution
    from release_files import SAFE_NAME, regular_file as _regular_file
    from release_files import sha256_file as _sha256


def _write_manifest(root: Path, relative_paths: list[Path], destination: Path) -> None:
    rows = [f"{_sha256(root / path)}  {path.as_posix()}" for path in relative_paths]
    destination.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _copy(source: Path, destination: Path) -> None:
    source = _regular_file(source, "release input")
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o644)


def prepare_release_bundle(
    dist: Path,
    wheelhouse: Path,
    lock: Path,
    output: Path,
    version: str,
    platform_label: str,
) -> dict[str, Any]:
    if not version or SAFE_NAME.fullmatch(version) is None:
        raise ValueError("release version must be a safe non-empty identifier")
    if not platform_label or SAFE_NAME.fullmatch(platform_label) is None:
        raise ValueError("platform label must be a safe non-empty identifier")
    for directory, label in ((dist, "distribution directory"), (wheelhouse, "wheelhouse")):
        metadata = directory.stat(follow_symlinks=False)
        if directory.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"{label} must be a non-symlink directory: {directory}")
    _regular_file(lock, "governance lock")
    if output.exists() or output.is_symlink():
        output_metadata = output.stat(follow_symlinks=False)
        if output.is_symlink() or not stat.S_ISDIR(output_metadata.st_mode):
            raise ValueError(f"release output must be a non-symlink directory: {output}")
        if any(output.iterdir()):
            raise ValueError(f"release output must be absent or empty: {output}")

    distributions = sorted(
        (_regular_file(path, "distribution") for path in dist.iterdir()),
        key=lambda path: path.name,
    )
    project_wheels = [path for path in distributions if path.suffix == ".whl"]
    source_archives = [path for path in distributions if path.name.endswith(".tar.gz")]
    if len(project_wheels) != 1 or len(source_archives) != 1 or len(distributions) != 2:
        raise ValueError("dist must contain exactly one wheel and one .tar.gz source archive")
    dependency_wheels = sorted(
        (_regular_file(path, "dependency wheel") for path in wheelhouse.iterdir()),
        key=lambda path: path.name,
    )
    if not dependency_wheels or any(path.suffix != ".whl" for path in dependency_wheels):
        raise ValueError("wheelhouse must contain only one or more dependency wheels")

    output.mkdir(parents=True, exist_ok=True)
    release_distributions = output / "distributions"
    offline = output / "offline"
    offline_distributions = offline / "distributions"
    offline_wheelhouse = offline / "wheelhouse"
    release_distributions.mkdir()
    offline_distributions.mkdir(parents=True)
    offline_wheelhouse.mkdir()

    for source in distributions:
        _copy(source, release_distributions / source.name)
    _copy(project_wheels[0], offline_distributions / project_wheels[0].name)
    for source in dependency_wheels:
        _copy(source, offline_wheelhouse / source.name)
    _copy(lock, offline / "requirements-governance.lock")

    offline_paths = sorted(
        (
            path.relative_to(offline)
            for path in offline.rglob("*")
            if path.is_file()
        ),
        key=lambda path: path.as_posix(),
    )
    _write_manifest(offline, offline_paths, offline / "SHA256SUMS.txt")

    archive_name = f"agentic-sdd-governance-{version}-offline-{platform_label}.zip"
    archive = output / archive_name
    archive_root = archive_name.removesuffix(".zip")
    archive_paths = [Path("SHA256SUMS.txt"), *offline_paths]
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for relative in archive_paths:
            source = offline / relative
            information = zipfile.ZipInfo(
                f"{archive_root}/{relative.as_posix()}",
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            information.compress_type = zipfile.ZIP_DEFLATED
            information.create_system = 3
            information.external_attr = (stat.S_IFREG | 0o644) << 16
            bundle.writestr(information, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    os.chmod(archive, 0o644)

    public_assets = [
        *(release_distributions / path.name for path in distributions),
        archive,
    ]
    manifest_rows = [f"{_sha256(path)}  {path.name}" for path in public_assets]
    (output / "SHA256SUMS.txt").write_text(
        "\n".join(sorted(manifest_rows)) + "\n", encoding="utf-8"
    )
    return {
        "ok": True,
        "version": version,
        "platform_label": platform_label,
        "project_wheel": project_wheels[0].name,
        "dependency_wheel_count": len(dependency_wheels),
        "offline_archive": archive.name,
        "public_asset_count": len(public_assets) + 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--wheelhouse", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform-label", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = prepare_release_bundle(
            args.dist,
            args.wheelhouse,
            args.lock,
            args.output,
            args.version,
            args.platform_label,
        )
    except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
        report = {"ok": False, "error": str(exc)}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report is not None:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
