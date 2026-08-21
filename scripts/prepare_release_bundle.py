#!/usr/bin/env python3
"""Build a deterministic, hash-inventoried offline release bundle."""

from __future__ import annotations

import argparse
import email.policy
import json
import re
import stat
import tarfile
import zipfile
from contextlib import ExitStack
from email.parser import BytesParser
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import (
    InvalidSdistFilename,
    InvalidWheelFilename,
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import InvalidVersion, Version

if __package__:
    from .release_files import (
        SAFE_NAME,
        OpenedDirectory,
        OpenedRegularFile,
        open_directory,
        open_regular_file,
    )
else:  # pragma: no cover - exercised by direct release workflow execution
    from release_files import (
        SAFE_NAME,
        OpenedDirectory,
        OpenedRegularFile,
        open_directory,
        open_regular_file,
    )


def _manifest_bytes(root: OpenedDirectory, relative_paths: list[Path]) -> bytes:
    rows: list[str] = []
    for relative in relative_paths:
        with root.open_relative_regular_file(
            relative, "release manifest input"
        ) as source:
            rows.append(f"{source.sha256()}  {relative.as_posix()}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def _copy(
    source: OpenedRegularFile, destination: OpenedDirectory, name: str
) -> None:
    source.copy_to_at(destination, name, mode=0o644)


def _locked_requirements(
    lock: OpenedRegularFile,
) -> dict[str, tuple[Version, set[str]]]:
    logical_rows: list[str] = []
    pending: list[str] = []
    for raw in lock.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        continued = stripped.endswith("\\")
        pending.append(stripped[:-1].strip() if continued else stripped)
        if not continued:
            logical_rows.append(" ".join(pending))
            pending = []
    if pending:
        raise ValueError("governance lock has an unterminated continuation")

    locked: dict[str, tuple[Version, set[str]]] = {}
    for row in logical_rows:
        fields = row.split()
        try:
            requirement = Requirement(fields[0])
        except (IndexError, InvalidRequirement) as exc:
            raise ValueError("governance lock contains an invalid requirement") from exc
        specifiers = list(requirement.specifier)
        if (
            requirement.url is not None
            or requirement.extras
            or requirement.marker is not None
            or len(specifiers) != 1
            or specifiers[0].operator != "=="
            or specifiers[0].version.endswith(".*")
        ):
            raise ValueError("governance lock requirements must be exact pins")
        hashes: set[str] = set()
        for field in fields[1:]:
            match = re.fullmatch(r"--hash=sha256:([a-f0-9]{64})", field)
            if match is None:
                raise ValueError("governance lock contains an unsupported option")
            hashes.add(match.group(1))
        if not hashes:
            raise ValueError("governance lock requirement has no SHA-256 hashes")
        name = str(canonicalize_name(requirement.name))
        if name in locked:
            raise ValueError("governance lock contains a duplicate requirement")
        try:
            locked[name] = (Version(specifiers[0].version), hashes)
        except InvalidVersion as exc:
            raise ValueError("governance lock contains an invalid version") from exc
    if not locked:
        raise ValueError("governance lock contains no requirements")
    return locked


def _metadata_identity(raw: bytes, label: str) -> tuple[str, Version]:
    message = BytesParser(policy=email.policy.compat32).parsebytes(raw)
    names = message.get_all("Name", [])
    versions = message.get_all("Version", [])
    if len(names) != 1 or len(versions) != 1:
        raise ValueError(f"{label} metadata must declare one Name and Version")
    try:
        version = Version(versions[0])
    except InvalidVersion as exc:
        raise ValueError(f"{label} metadata contains an invalid version") from exc
    return str(canonicalize_name(names[0])), version


def _wheel_identity(path: OpenedRegularFile, label: str) -> tuple[str, Version]:
    try:
        filename_name, filename_version, _build, _tags = parse_wheel_filename(path.name)
    except InvalidWheelFilename as exc:
        raise ValueError(f"{label} has an invalid wheel filename") from exc
    try:
        with path.binary_stream() as handle, zipfile.ZipFile(handle) as archive:
            candidates = [
                member
                for member in archive.infolist()
                if not member.is_dir()
                and len(PurePosixPath(member.filename).parts) == 2
                and PurePosixPath(member.filename).parts[0].endswith(".dist-info")
                and PurePosixPath(member.filename).name == "METADATA"
            ]
            if len(candidates) != 1 or candidates[0].file_size > 1024 * 1024:
                raise ValueError(f"{label} must contain one bounded METADATA file")
            metadata_name, metadata_version = _metadata_identity(
                archive.read(candidates[0]), label
            )
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{label} is not a valid wheel archive") from exc
    normalized_filename_name = str(filename_name)
    if (
        metadata_name != normalized_filename_name
        or metadata_version != filename_version
    ):
        raise ValueError(f"{label} filename and metadata name/version do not match")
    return normalized_filename_name, filename_version


def _sdist_identity(path: OpenedRegularFile) -> tuple[str, Version]:
    try:
        filename_name, filename_version = parse_sdist_filename(path.name)
    except InvalidSdistFilename as exc:
        raise ValueError("source archive has an invalid filename") from exc
    try:
        with path.binary_stream() as handle, tarfile.open(
            fileobj=handle, mode="r:gz"
        ) as archive:
            candidates = [
                member
                for member in archive.getmembers()
                if len(PurePosixPath(member.name).parts) == 2
                and PurePosixPath(member.name).name == "PKG-INFO"
            ]
            if (
                len(candidates) != 1
                or not candidates[0].isreg()
                or candidates[0].size > 1024 * 1024
            ):
                raise ValueError("source archive must contain one bounded PKG-INFO file")
            extracted = archive.extractfile(candidates[0])
            if extracted is None:
                raise ValueError("source archive PKG-INFO is unavailable")
            metadata_name, metadata_version = _metadata_identity(
                extracted.read(), "source archive"
            )
    except tarfile.TarError as exc:
        raise ValueError("source archive is not a valid tar archive") from exc
    normalized_filename_name = str(filename_name)
    if (
        metadata_name != normalized_filename_name
        or metadata_version != filename_version
    ):
        raise ValueError(
            "source archive filename and metadata name/version do not match"
        )
    return normalized_filename_name, filename_version


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
    with ExitStack() as inputs:
        dist_directory = inputs.enter_context(
            open_directory(dist, "distribution directory")
        )
        wheelhouse_directory = inputs.enter_context(
            open_directory(wheelhouse, "wheelhouse")
        )
        lock_source = inputs.enter_context(
            open_regular_file(lock, "governance lock")
        )
        distributions = sorted(
            (
                inputs.enter_context(
                    dist_directory.open_regular_file(name, "distribution")
                )
                for name in dist_directory.names()
            ),
            key=lambda path: path.name,
        )
        project_wheels = [path for path in distributions if path.suffix == ".whl"]
        source_archives = [
            path for path in distributions if path.name.endswith(".tar.gz")
        ]
        if (
            len(project_wheels) != 1
            or len(source_archives) != 1
            or len(distributions) != 2
        ):
            raise ValueError(
                "dist must contain exactly one wheel and one .tar.gz source archive"
            )
        dependency_wheels = sorted(
            (
                inputs.enter_context(
                    wheelhouse_directory.open_regular_file(
                        name, "dependency wheel"
                    )
                )
                for name in wheelhouse_directory.names()
            ),
            key=lambda path: path.name,
        )
        if not dependency_wheels or any(
            path.suffix != ".whl" for path in dependency_wheels
        ):
            raise ValueError(
                "wheelhouse must contain only one or more dependency wheels"
            )

        try:
            expected_version = Version(version)
        except InvalidVersion as exc:
            raise ValueError("release version is invalid") from exc
        project_name, project_version = _wheel_identity(
            project_wheels[0], "project wheel"
        )
        source_name, source_version = _sdist_identity(source_archives[0])
        if (
            project_name != source_name
            or project_version != expected_version
            or source_version != expected_version
        ):
            raise ValueError(
                "project wheel and source archive version must match the release"
            )

        locked = _locked_requirements(lock_source)
        wheel_names: set[str] = set()
        for dependency in dependency_wheels:
            dependency_name, dependency_version = _wheel_identity(
                dependency, "dependency wheel"
            )
            if dependency_name in wheel_names:
                raise ValueError("wheelhouse contains duplicate dependency packages")
            wheel_names.add(dependency_name)
            locked_row = locked.get(dependency_name)
            if locked_row is None or dependency_version != locked_row[0]:
                raise ValueError(
                    "dependency wheel is not an exact locked requirement"
                )
            if dependency.sha256() not in locked_row[1]:
                raise ValueError(
                    "dependency wheel digest is absent from the locked hashes"
                )
        if wheel_names != set(locked):
            raise ValueError("wheelhouse does not exactly cover the governance lock")

        output_directory = inputs.enter_context(
            open_directory(output, "release output", create=True)
        )
        if output_directory.names():
            raise ValueError(f"release output must be absent or empty: {output}")
        release_distributions = inputs.enter_context(
            output_directory.make_directory(
                "distributions", "release distributions"
            )
        )
        offline = inputs.enter_context(
            output_directory.make_directory("offline", "offline release")
        )
        offline_distributions = inputs.enter_context(
            offline.make_directory("distributions", "offline distributions")
        )
        offline_wheelhouse = inputs.enter_context(
            offline.make_directory("wheelhouse", "offline wheelhouse")
        )

        for source in distributions:
            _copy(source, release_distributions, source.name)
        _copy(
            project_wheels[0],
            offline_distributions,
            project_wheels[0].name,
        )
        for source in dependency_wheels:
            _copy(source, offline_wheelhouse, source.name)
        _copy(lock_source, offline, "requirements-governance.lock")

        offline_paths = sorted(
            [
                Path("distributions") / project_wheels[0].name,
                *(Path("wheelhouse") / source.name for source in dependency_wheels),
                Path("requirements-governance.lock"),
            ],
            key=lambda path: path.as_posix(),
        )
        offline.write_bytes(
            "SHA256SUMS.txt", _manifest_bytes(offline, offline_paths)
        )

        archive_name = (
            f"agentic-sdd-governance-{version}-offline-{platform_label}.zip"
        )
        archive_root = archive_name.removesuffix(".zip")
        archive_paths = [Path("SHA256SUMS.txt"), *offline_paths]
        with (
            output_directory.binary_writer(archive_name) as archive_handle,
            zipfile.ZipFile(
                archive_handle,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as bundle,
        ):
            for relative in archive_paths:
                information = zipfile.ZipInfo(
                    f"{archive_root}/{relative.as_posix()}",
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                information.compress_type = zipfile.ZIP_DEFLATED
                information.create_system = 3
                information.external_attr = (stat.S_IFREG | 0o644) << 16
                with offline.open_relative_regular_file(
                    relative, "offline bundle asset"
                ) as asset:
                    bundle.writestr(
                        information,
                        asset.read_bytes(),
                        compress_type=zipfile.ZIP_DEFLATED,
                    )
        public_rows: list[tuple[str, str]] = []
        for source in distributions:
            with release_distributions.open_regular_file(
                source.name, "public distribution"
            ) as published:
                public_rows.append((source.name, published.sha256()))
        with output_directory.open_regular_file(
            archive_name, "public offline archive"
        ) as archive:
            public_rows.append((archive_name, archive.sha256()))
        public_rows.sort()
        output_directory.write_bytes(
            "SHA256SUMS.txt",
            (
                "\n".join(f"{digest}  {name}" for name, digest in public_rows)
                + "\n"
            ).encode("utf-8"),
        )
        return {
            "ok": True,
            "version": version,
            "platform_label": platform_label,
            "project_wheel": project_wheels[0].name,
            "dependency_wheel_count": len(dependency_wheels),
            "offline_archive": archive_name,
            # Public assets include the distributions, offline archive, and
            # SHA256SUMS.txt itself.
            "public_asset_count": len(public_rows) + 1,
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
    except (
        EOFError,
        FileNotFoundError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
    ) as exc:
        report = {"ok": False, "error": str(exc)}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
