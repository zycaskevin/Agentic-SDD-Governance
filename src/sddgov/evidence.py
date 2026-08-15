from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path, PurePosixPath

from .redaction import TEXT_SUFFIXES, redact_files, redact_text
from .schema_validation import bundled_schema, validate_instance


COLLECTORS = {
    "browser-console", "browser-har", "playwright-trace", "flutter-log",
    "android-logcat", "supabase-log", "docker-log", "terminal", "git",
}
PHASES = ("red", "evidence", "fix", "green", "proof")
DEP_ID_PATTERN = re.compile(r"^DEP-[A-Za-z0-9._-]+$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
REQUIRED_DOCS = {
    "red": ("reproduction.md",),
    "evidence": ("reproduction.md", "redaction-report.json"),
    "fix": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "redaction-report.json"),
    "green": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "regression-evidence.md", "verification.md", "redaction-report.json"),
    "proof": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "regression-evidence.md", "verification.md", "rollback.md", "redaction-report.json"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resource_dir():
    return resources.files("sddgov").joinpath("resources/dep")


@contextmanager
def _opened_directory_path(path: Path, *, create: bool):
    """Walk an absolute directory path without following mutable components."""
    candidate = path if path.is_absolute() else Path.cwd() / path
    if sys.platform == "darwin" and candidate.parts[:2] == ("/", "var"):
        candidate = Path("/private/var").joinpath(*candidate.parts[2:])
    if any(part in {"", ".", ".."} for part in candidate.parts[1:]):
        raise ValueError("directory path is not normalized")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    anchor = Path(candidate.anchor or os.sep)
    descriptors = [os.open(anchor, directory_flags)]
    components: list[str] = []
    try:
        for part in candidate.parts[1:]:
            try:
                child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=descriptors[-1])
                child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            except OSError as exc:
                raise ValueError(
                    f"directory path cannot be opened safely: {candidate}"
                ) from exc
            metadata = os.fstat(child)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child)
                raise ValueError(f"directory path component is unsafe: {candidate}")
            descriptors.append(child)
            components.append(part)
        yield candidate, descriptors[-1]
        for index, part in enumerate(components):
            try:
                current = os.stat(
                    part, dir_fd=descriptors[index], follow_symlinks=False
                )
            except OSError as exc:
                raise ValueError(
                    f"directory path changed during operation: {candidate}"
                ) from exc
            opened = os.fstat(descriptors[index + 1])
            if (
                stat.S_ISLNK(current.st_mode)
                or not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                raise ValueError(
                    f"directory path changed during operation: {candidate}"
                )
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@contextmanager
def _opened_dep_root(dep: Path):
    if dep.is_symlink() or not dep.exists() or not dep.is_dir():
        raise ValueError("DEP root must be an existing non-symlink directory")
    before = dep.lstat()
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(dep, directory_flags)
    try:
        opened_root = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (opened_root.st_dev, opened_root.st_ino):
            raise ValueError("DEP root changed while it was being opened")
        yield descriptor
        after = dep.lstat()
        if (
            stat.S_ISLNK(after.st_mode)
            or not stat.S_ISDIR(after.st_mode)
            or (after.st_dev, after.st_ino) != (opened_root.st_dev, opened_root.st_ino)
        ):
            raise ValueError("DEP root changed during the Evidence operation")
    finally:
        os.close(descriptor)


@contextmanager
def _opened_zone_at(root_fd: int, relative: Path, *, create: bool = True):
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"evidence zone is not normalized: {relative}")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptors = [os.dup(root_fd)]
    components: list[str] = []
    try:
        for part in relative.parts:
            try:
                child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, dir_fd=descriptors[-1])
                child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            except OSError as exc:
                raise ValueError(f"evidence zone cannot be opened safely: {relative}") from exc
            metadata = os.fstat(child)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child)
                raise ValueError(f"evidence zone component is not a directory: {relative}")
            descriptors.append(child)
            components.append(part)
        yield descriptors[-1]
        for index, part in enumerate(components):
            try:
                current = os.stat(
                    part, dir_fd=descriptors[index], follow_symlinks=False
                )
            except OSError as exc:
                raise ValueError(
                    f"evidence zone changed during operation: {relative}"
                ) from exc
            opened = os.fstat(descriptors[index + 1])
            if (
                stat.S_ISLNK(current.st_mode)
                or not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                raise ValueError(f"evidence zone changed during operation: {relative}")
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@contextmanager
def _bounded_zone(dep: Path, relative: Path, *, create: bool = True):
    dep_root = dep.resolve(strict=True)
    candidate = dep_root.joinpath(*relative.parts)
    with _opened_dep_root(dep) as root_fd:
        with _opened_zone_at(root_fd, relative, create=create) as zone_fd:
            yield candidate, zone_fd


def _bounded_filename(directory: Path, name: str) -> Path:
    if not name or name in {".", ".."} or name.rstrip(" .") != name:
        raise ValueError("evidence filename is unsafe after platform normalization")
    candidate_path = directory / name
    if candidate_path.is_symlink():
        raise ValueError("evidence destination must not be a symlink")
    candidate = candidate_path.resolve()
    if candidate.parent != directory.resolve():
        raise ValueError("evidence destination escapes its collector zone")
    return candidate


def _require_regular_file(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise FileNotFoundError(path) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular file")
    if metadata.st_nlink != 1:
        raise ValueError(f"{label} must not be hard-linked")


def _read_regular_bytes(path: Path, label: str) -> bytes:
    """Read a file while retaining and rechecking its complete parent chain."""
    with _opened_directory_path(path.parent, create=False) as (_, parent_fd):
        raw, _ = _read_regular_bytes_at(parent_fd, path.name, label)
        return raw


def _read_regular_bytes_at(directory_fd: int, name: str, label: str) -> tuple[bytes, os.stat_result]:
    """Read one direct child through a retained directory descriptor."""
    if not name or Path(name).name != name:
        raise ValueError(f"{label} has an invalid filename")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except FileNotFoundError:
        raise
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError(f"{label} must not be a symlink") from exc
        raise ValueError(f"{label} cannot be opened safely: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"{label} must be a regular file")
        if metadata.st_nlink != 1:
            raise ValueError(f"{label} must not be hard-linked")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks), metadata
    finally:
        os.close(descriptor)


def _load_at(directory_fd: int, name: str) -> dict:
    raw, _ = _read_regular_bytes_at(
        directory_fd, name, f"machine-readable document {name}"
    )
    return json.loads(raw.decode("utf-8"))


def _write_bytes_at(directory_fd: int, name: str, encoded: bytes, label: str) -> None:
    """Atomically replace one direct child without reopening its parent path."""
    if not name or Path(name).name != name:
        raise ValueError(f"{label} has an invalid filename")
    try:
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        current = None
    if current is not None and stat.S_ISLNK(current.st_mode):
        raise ValueError(f"{label} must not be a symlink: {name}")
    if current is not None and (
        not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
    ):
        raise ValueError(
            f"{label} must be a single-linked regular file: {name}"
        )
    temporary = f".{name}.tmp-{uuid.uuid4().hex}"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(
            temporary,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        os.fsync(directory_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def _save_at(directory_fd: int, name: str, data: dict) -> None:
    """Atomically replace one control document through its retained DEP fd."""
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write_bytes_at(directory_fd, name, encoded, "machine-readable destination")


def _attachment_write_transaction(
    dep_fd: int,
    output_fd: int,
    name: str,
    encoded: bytes,
    control_identities: dict[str, tuple[int, int, int, int]],
) -> None:
    """Write an attachment and roll it back if verified controls changed."""
    try:
        previous, _ = _read_regular_bytes_at(
            output_fd, name, "existing attachment output"
        )
    except FileNotFoundError:
        previous = None

    _require_control_snapshot(dep_fd, control_identities)
    _write_bytes_at(output_fd, name, encoded, "attachment output")
    written = os.stat(name, dir_fd=output_fd, follow_symlinks=False)
    written_identity = (written.st_dev, written.st_ino)
    try:
        _require_control_snapshot(dep_fd, control_identities)
    except ValueError:
        try:
            current = os.stat(name, dir_fd=output_fd, follow_symlinks=False)
        except OSError as exc:
            raise ValueError(
                "attachment output changed before rollback could be verified"
            ) from exc
        if (current.st_dev, current.st_ino) != written_identity:
            raise ValueError(
                "attachment output changed before rollback could be applied"
            )
        if previous is None:
            os.unlink(name, dir_fd=output_fd)
            os.fsync(output_fd)
        else:
            _write_bytes_at(
                output_fd,
                name,
                previous,
                "attachment output rollback",
            )
        raise


def _artifact_media_type(suffix: str, raw: bytes) -> str:
    normalized = suffix.lower()
    if normalized == ".har":
        return "application/har+json"
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    if (
        isinstance(parsed, dict)
        and isinstance(parsed.get("log"), dict)
        and isinstance(parsed["log"].get("entries"), list)
    ):
        return "application/har+json"
    if normalized in TEXT_SUFFIXES:
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            return "application/octet-stream"
        return "text/plain; charset=utf-8"
    return "application/octet-stream"


def _manifest_artifact_path(dep: Path, value: object, zone: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"artifact path is invalid for {zone}")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or str(pure) != value
        or any(part in {"", ".", ".."} for part in pure.parts)
        or tuple(pure.parts[: len(PurePosixPath(zone).parts)])
        != PurePosixPath(zone).parts
        or pure.parent != PurePosixPath(zone)
    ):
        raise ValueError(f"artifact path escapes or is not normalized for {zone}: {value}")
    candidate = dep.joinpath(*pure.parts)
    current = dep
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"artifact path contains a symlink: {value}")
    try:
        candidate.absolute().relative_to(dep.absolute())
    except ValueError as exc:
        raise ValueError(f"artifact path escapes DEP root: {value}") from exc
    return candidate


def _actual_zone_files_at(directory_fd: int, zone: str) -> tuple[set[str], list[str]]:
    actual: set[str] = set()
    errors: list[str] = []
    for name in os.listdir(directory_fd):
        relative = f"{zone}/{name}"
        if not name or Path(name).name != name:
            errors.append(f"artifact filename is not normalized: {relative}")
            continue
        try:
            metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as exc:
            errors.append(f"artifact cannot be inspected safely: {relative}: {exc}")
            continue
        if stat.S_ISLNK(metadata.st_mode):
            errors.append(f"artifact path contains a symlink: {relative}")
        elif not stat.S_ISREG(metadata.st_mode):
            errors.append(f"artifact path is not a regular file: {relative}")
        elif metadata.st_nlink != 1:
            errors.append(f"artifact path must not be hard-linked: {relative}")
        else:
            actual.add(relative)
    return actual, errors


def make_dep(base: Path, issue: str, risk: str, sdd_ref: str | None = None, dep_id: str | None = None) -> Path:
    if risk not in {"L0", "L1", "L2", "L3"}:
        raise ValueError("risk must be L0, L1, L2, or L3")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_issue = "".join(c if c.isalnum() or c in "-_" else "-" for c in issue).strip("-") or "untracked"
    dep_id = dep_id or f"DEP-{stamp}-{safe_issue}"
    if not DEP_ID_PATTERN.fullmatch(dep_id):
        raise ValueError("DEP ID must match DEP-[A-Za-z0-9._-]+ and cannot contain a path")
    summary = {
        "$schema": "../../schemas/debug-evidence-package.schema.json",
        "schema_version": "1.0",
        "dep_id": dep_id,
        "issue": issue,
        "sdd_references": [sdd_ref] if sdd_ref else [],
        "risk_level": risk,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "workflow": {"phase": "red", "history": [{"phase": "red", "at": utc_now()}]},
        "expected_behavior": "TODO",
        "actual_behavior": "TODO",
        "environment": {"commit": "TODO", "branch": "TODO", "runtime": "TODO"},
        "root_cause_status": "unknown",
        "attachments": [],
    }
    with _opened_directory_path(base, create=True) as (safe_base, base_fd):
        try:
            os.stat(dep_id, dir_fd=base_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(f"DEP already exists: {safe_base / dep_id}")
        with _opened_zone_at(base_fd, Path(dep_id), create=True) as dep_fd:
            with _opened_zone_at(dep_fd, Path("private/raw"), create=True) as raw_fd:
                with _opened_zone_at(
                    dep_fd, Path("shareable/artifacts"), create=True
                ):
                    os.fchmod(raw_fd, 0o700)
                    for item in _resource_dir().iterdir():
                        if item.name == "summary.yaml":
                            continue
                        _write_bytes_at(
                            dep_fd,
                            item.name,
                            item.read_bytes(),
                            "DEP template destination",
                        )
                    _save_at(dep_fd, "summary.yaml", summary)
                    _save_at(
                        dep_fd,
                        "manifest.json",
                        {
                            "schema_version": "1.0",
                            "dep_id": dep_id,
                            "raw": [],
                            "shareable": [],
                        },
                    )
        return safe_base / dep_id


def collect(dep: Path, collector: str, input_path: Path, label: str | None = None) -> Path:
    if collector not in COLLECTORS:
        raise ValueError(f"unsupported collector: {collector}")
    raw = _read_regular_bytes(input_path, "collector input")
    with _opened_dep_root(dep) as dep_fd:
        manifest = _load_at(dep_fd, "manifest.json")
        ordinal = len(manifest.get("raw", [])) + 1
        source_suffix = input_path.suffix.lower()
        default_label = f"artifact-{ordinal}{source_suffix}"
        requested_label = label or default_label
        if requested_label.rstrip(" .") != requested_label:
            raise ValueError("evidence filename is unsafe after platform normalization")
        safe_label = "".join(
            c if c.isalnum() or c in "-_." else "-" for c in requested_label
        )
        label_suffix = Path(safe_label).suffix.lower()
        if label_suffix and label_suffix != source_suffix:
            raise ValueError("evidence label suffix must match the collector input type")
        if not label_suffix:
            safe_label += source_suffix
        filename = f"{collector}--{safe_label}"
        raw_dir = dep.resolve(strict=True) / "private" / "raw"
        with _opened_zone_at(dep_fd, Path("private/raw"), create=False) as raw_dir_fd:
            os.fchmod(raw_dir_fd, 0o700)
            destination = _bounded_filename(raw_dir, filename)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(filename, flags, 0o600, dir_fd=raw_dir_fd)
            except FileExistsError as exc:
                raise FileExistsError(f"Evidence artifact already exists: {filename}") from exc
            try:
                view = memoryview(raw)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            digest = hashlib.sha256(raw).hexdigest()
            manifest["raw"].append({
                "collector": collector,
                "path": f"private/raw/{filename}",
                "source_suffix": source_suffix,
                "media_type": _artifact_media_type(source_suffix, raw),
                "sha256": digest,
                "size": len(raw),
                "collected_at": utc_now(),
                "shareable": False,
            })
            _save_at(dep_fd, "manifest.json", manifest)
        return destination


def redact(dep: Path) -> dict:
    with _opened_dep_root(dep) as dep_fd:
        manifest = _load_at(dep_fd, "manifest.json")
        raw_rows = manifest.get("raw", [])
        if not isinstance(raw_rows, list):
            raise ValueError("Evidence manifest raw must be an array")
        raw_by_name = {
            Path(row.get("path", "")).name: row
            for row in raw_rows
            if isinstance(row, dict)
        }
        if len(raw_by_name) != len(raw_rows):
            raise ValueError("Evidence manifest contains duplicate or invalid raw paths")
        dep_root = dep.resolve(strict=True)
        raw_dir = dep_root / "private" / "raw"
        shareable = dep_root / "shareable" / "artifacts"
        with _opened_zone_at(dep_fd, Path("private/raw"), create=False) as raw_dir_fd:
            with _opened_zone_at(
                dep_fd, Path("shareable/artifacts"), create=False
            ) as shareable_fd:
                names = sorted(os.listdir(raw_dir_fd))
                files = [raw_dir / name for name in names]
                report = redact_files(
                files,
                shareable,
                metadata_by_name=raw_by_name,
                source_dir_fd=raw_dir_fd,
                output_dir_fd=shareable_fd,
                )
                report["dep_id"] = _load_at(dep_fd, "summary.yaml")["dep_id"]
                report["generated_at"] = utc_now()
                observed_raw = {
                    row["source"]: (row["source_sha256"], row["source_size"])
                    for row in report["files"]
                }
                observed_raw.update(
                    {
                        row["file"]: (row["sha256"], row["size"])
                        for row in report["blocked"]
                    }
                )
                for name, row in raw_by_name.items():
                    observed = observed_raw.get(name)
                    if observed is None:
                        raise ValueError(f"raw artifact is not covered by redaction: {name}")
                    row["sha256"], row["size"] = observed
                manifest["shareable"] = [
                    {
                        "path": f"shareable/artifacts/{row['output']}",
                        "sha256": row["output_sha256"],
                        "size": row["output_size"],
                        "shareable": True,
                    }
                    for row in report["files"]
                ]
                _save_at(dep_fd, "redaction-report.json", report)
                _save_at(dep_fd, "manifest.json", manifest)
                return report


def transition(dep: Path, phase: str) -> dict:
    if phase not in PHASES:
        raise ValueError(f"phase must be one of: {', '.join(PHASES)}")
    with _opened_dep_root(dep) as dep_fd:
        summary = _load_at(dep_fd, "summary.yaml")
        current = summary["workflow"]["phase"]
        if PHASES.index(phase) != PHASES.index(current) + 1:
            raise ValueError(f"transition must advance exactly one phase: {current} -> {phase}")
        previous = json.loads(json.dumps(summary))
        summary["workflow"]["phase"] = phase
        summary["workflow"]["history"].append({"phase": phase, "at": utc_now()})
        summary["updated_at"] = utc_now()
        _save_at(dep_fd, "summary.yaml", summary)
        errors = verify(dep, strict=False)
        if errors:
            _save_at(dep_fd, "summary.yaml", previous)
            raise ValueError(f"cannot enter {phase}: " + "; ".join(errors))
        return summary


def _verify_manifest_artifacts(
    dep: Path, dep_fd: int, manifest: dict, *, portable: bool
) -> list[str]:
    errors: list[str] = []
    expected_paths: dict[str, set[str]] = {
        "private/raw": set(),
        "shareable/artifacts": set(),
    }
    row_contracts = {
        "raw": {
            "collector", "path", "source_suffix", "media_type", "sha256", "size",
            "collected_at", "shareable"
        },
        "shareable": {"path", "sha256", "size", "shareable"},
    }
    for kind, zone in (("raw", "private/raw"), ("shareable", "shareable/artifacts")):
        rows = manifest.get(kind)
        if not isinstance(rows, list):
            errors.append(f"manifest {kind} must be an array")
            continue
        zone_fd: int | None = None
        zone_context = _opened_zone_at(dep_fd, Path(zone), create=False)
        try:
            zone_fd = zone_context.__enter__()
        except FileNotFoundError:
            if not (portable and kind == "raw"):
                errors.append(f"missing artifact zone: {zone}")
        try:
            for index, row in enumerate(rows):
                label = f"manifest {kind}[{index}]"
                if not isinstance(row, dict) or set(row) != row_contracts[kind]:
                    errors.append(f"{label} has an invalid contract")
                    continue
                if kind == "raw" and row.get("collector") not in COLLECTORS:
                    errors.append(f"{label} has an unsupported collector")
                if kind == "raw" and (
                    not isinstance(row.get("source_suffix"), str)
                    or row["source_suffix"] != Path(str(row.get("path", ""))).suffix.lower()
                ):
                    errors.append(f"{label} source_suffix does not match its immutable path")
                if kind == "raw" and row.get("media_type") not in {
                    "application/har+json",
                    "application/octet-stream",
                    "text/plain; charset=utf-8",
                }:
                    errors.append(f"{label} media_type is invalid")
                if kind == "raw" and (
                    not isinstance(row.get("collected_at"), str)
                    or not row["collected_at"].strip()
                ):
                    errors.append(f"{label} collected_at is invalid")
                expected_shareable = kind == "shareable"
                if row.get("shareable") is not expected_shareable:
                    errors.append(f"{label} shareable flag is invalid")
                if (
                    not isinstance(row.get("size"), int)
                    or isinstance(row.get("size"), bool)
                    or row["size"] < 0
                ):
                    errors.append(f"{label} size is invalid")
                if not isinstance(row.get("sha256"), str) or not SHA256_PATTERN.fullmatch(
                    row["sha256"]
                ):
                    errors.append(f"{label} sha256 is invalid")
                try:
                    path = _manifest_artifact_path(dep, row.get("path"), zone)
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                relative = path.relative_to(dep).as_posix()
                if relative in expected_paths[zone]:
                    errors.append(f"duplicate manifest artifact path: {relative}")
                    continue
                expected_paths[zone].add(relative)
                if zone_fd is None:
                    if not (portable and kind == "raw"):
                        errors.append(f"missing artifact: {relative}")
                    continue
                try:
                    artifact, metadata = _read_regular_bytes_at(
                        zone_fd, path.name, f"artifact {relative}"
                    )
                except FileNotFoundError:
                    if not (portable and kind == "raw"):
                        errors.append(f"missing artifact: {relative}")
                    continue
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                if isinstance(row.get("size"), int) and metadata.st_size != row["size"]:
                    errors.append(f"artifact size mismatch: {relative}")
                if (
                    isinstance(row.get("sha256"), str)
                    and hashlib.sha256(artifact).hexdigest() != row["sha256"]
                ):
                    errors.append(f"artifact sha256 mismatch: {relative}")
                if kind == "raw":
                    detected = _artifact_media_type(row.get("source_suffix", ""), artifact)
                    if row.get("media_type") != detected:
                        errors.append(f"artifact media_type mismatch: {relative}")
            if zone_fd is not None:
                actual, zone_errors = _actual_zone_files_at(zone_fd, zone)
                errors.extend(zone_errors)
                extras = sorted(actual - expected_paths[zone])
                if extras:
                    errors.append(
                        f"unregistered artifacts in {zone}: " + ", ".join(extras)
                    )
        finally:
            if zone_fd is not None:
                zone_context.__exit__(None, None, None)
    return errors


def _verify_redaction_associations(
    dep: Path, dep_fd: int, manifest: dict, report: dict
) -> list[str]:
    errors: list[str] = []
    required_report = {
        "schema_version", "files", "blocked", "totals", "dep_id", "generated_at"
    }
    if set(report) != required_report or report.get("schema_version") != "1.0":
        return ["redaction report has an invalid contract"]
    if report.get("dep_id") != manifest.get("dep_id"):
        errors.append("redaction report dep_id does not match manifest")
    files = report.get("files")
    if not isinstance(files, list):
        return errors + ["redaction report files must be an array"]
    blocked = report.get("blocked")
    if not isinstance(blocked, list):
        return errors + ["redaction report blocked must be an array"]
    raw_rows = {
        Path(row["path"]).name: row
        for row in manifest.get("raw", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    shareable_rows = {
        Path(row["path"]).name: row
        for row in manifest.get("shareable", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    expected_fields = {
        "source", "output", "source_sha256", "source_size",
        "output_sha256", "output_size", "redactions",
    }
    seen_sources: set[str] = set()
    seen_blocked: set[str] = set()
    seen_outputs: set[str] = set()
    computed_totals: dict[str, int] = {}
    for index, row in enumerate(files):
        label = f"redaction report files[{index}]"
        if not isinstance(row, dict) or set(row) != expected_fields:
            errors.append(f"{label} has an invalid contract")
            continue
        source = row.get("source")
        output = row.get("output")
        if (
            not isinstance(source, str)
            or not source
            or Path(source).name != source
            or not isinstance(output, str)
            or not output
            or Path(output).name != output
        ):
            errors.append(f"{label} contains an invalid source or output name")
            continue
        if source in seen_sources or output in seen_outputs:
            errors.append(f"{label} duplicates a source or output association")
            continue
        seen_sources.add(source)
        seen_outputs.add(output)
        if Path(source).suffix.lower() not in TEXT_SUFFIXES:
            errors.append(f"{label} source type is not eligible for deterministic redaction")
        if Path(output).suffix.lower() not in TEXT_SUFFIXES:
            errors.append(f"{label} output type is not eligible for deterministic redaction")
        if Path(source).suffix.lower() != Path(output).suffix.lower():
            errors.append(f"{label} source and output types do not match")
        raw = raw_rows.get(source)
        shareable = shareable_rows.get(output)
        if raw is None or shareable is None:
            errors.append(f"{label} is not fully associated with manifest artifacts")
            continue
        if raw.get("collector") == "browser-har" or raw.get("media_type") == "application/har+json":
            errors.append(f"{label} HAR evidence must remain blocked")
        for report_key, manifest_key, manifest_row in (
            ("source_sha256", "sha256", raw),
            ("source_size", "size", raw),
            ("output_sha256", "sha256", shareable),
            ("output_size", "size", shareable),
        ):
            if row.get(report_key) != manifest_row.get(manifest_key):
                errors.append(f"{label} {report_key} does not match manifest")
        redactions = row.get("redactions")
        if not isinstance(redactions, dict) or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
            for key, value in redactions.items()
        ):
            errors.append(f"{label} redactions are invalid")
        else:
            for key, value in redactions.items():
                computed_totals[key] = computed_totals.get(key, 0) + value

        try:
            raw_path = _manifest_artifact_path(dep, raw["path"], "private/raw")
            output_path = _manifest_artifact_path(
                dep, shareable["path"], "shareable/artifacts"
            )
        except (KeyError, ValueError):
            continue
        if output_path.suffix.lower() in TEXT_SUFFIXES:
            try:
                with _opened_zone_at(
                    dep_fd, Path("shareable/artifacts"), create=False
                ) as shareable_fd:
                    output_bytes, _ = _read_regular_bytes_at(
                        shareable_fd, output_path.name, f"{label} shareable output"
                    )
                output_text = output_bytes.decode("utf-8")
            except FileNotFoundError:
                continue
            except UnicodeDecodeError:
                errors.append(f"{label} shareable text is not valid UTF-8")
            except ValueError as exc:
                errors.append(str(exc))
            else:
                rescanned_output, _ = redact_text(output_text)
                if rescanned_output != output_text:
                    errors.append(f"{label} shareable output still matches redaction rules")
                try:
                    with _opened_zone_at(
                        dep_fd, Path("private/raw"), create=False
                    ) as raw_fd:
                        raw_bytes, _ = _read_regular_bytes_at(
                            raw_fd, raw_path.name, f"{label} raw source"
                        )
                    raw_text = raw_bytes.decode("utf-8")
                except FileNotFoundError:
                    pass
                except UnicodeDecodeError:
                    errors.append(f"{label} raw text is not valid UTF-8")
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    expected_output, expected_redactions = redact_text(raw_text)
                    if output_text != expected_output:
                        errors.append(
                            f"{label} output is not the deterministic redaction of source"
                        )
                    if redactions != expected_redactions:
                        errors.append(
                            f"{label} redaction counts do not match recalculation"
                        )
    blocked_fields = {"file", "reason", "sha256", "size"}
    for index, row in enumerate(blocked):
        label = f"redaction report blocked[{index}]"
        if not isinstance(row, dict) or set(row) != blocked_fields:
            errors.append(f"{label} has an invalid contract")
            continue
        source = row.get("file")
        if (
            not isinstance(source, str)
            or not source
            or Path(source).name != source
            or not isinstance(row.get("reason"), str)
            or not row["reason"].strip()
        ):
            errors.append(f"{label} contains an invalid file or reason")
            continue
        if source in seen_sources or source in seen_blocked:
            errors.append(f"{label} duplicates or overlaps a raw association")
            continue
        seen_blocked.add(source)
        raw = raw_rows.get(source)
        if raw is None:
            errors.append(f"{label} is not associated with a manifest raw artifact")
            continue
        if row.get("sha256") != raw.get("sha256"):
            errors.append(f"{label} sha256 does not match manifest")
        if row.get("size") != raw.get("size"):
            errors.append(f"{label} size does not match manifest")
        if (
            raw.get("collector") == "browser-har"
            or raw.get("media_type") == "application/har+json"
        ) and row.get("reason") != "har_requires_dedicated_body_stripping":
            errors.append(f"{label} HAR block reason is invalid")

    if seen_sources | seen_blocked != set(raw_rows):
        errors.append("redaction report does not cover every raw artifact exactly once")
    if seen_outputs != set(shareable_rows):
        errors.append("redaction report does not cover every shareable artifact")
    if report.get("totals") != computed_totals:
        errors.append("redaction report totals do not match file associations")
    return errors


def _verify_open(
    dep: Path, dep_fd: int, strict: bool, portable: bool
) -> tuple[list[str], dict | None, dict | None, dict[str, tuple[int, int, int, int]]]:
    """Verify one immutable-in-memory snapshot of the DEP control documents."""
    errors: list[str] = []
    control_bytes: dict[str, bytes] = {}
    control_identities: dict[str, tuple[int, int, int, int]] = {}
    if portable and not strict:
        errors.append("portable verification requires strict mode")
    for name in ("summary.yaml", "manifest.json"):
        try:
            document, metadata = _read_regular_bytes_at(dep_fd, name, name)
            control_bytes[name] = document
            control_identities[name] = (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
            )
        except FileNotFoundError:
            errors.append(f"missing {name}")
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        return errors, None, None, control_identities
    try:
        summary = json.loads(control_bytes["summary.yaml"].decode("utf-8"))
        manifest = json.loads(control_bytes["manifest.json"].decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"invalid machine-readable document: {exc}"], None, None, control_identities
    try:
        errors.extend(
            f"summary schema: {error}"
            for error in validate_instance(
                summary,
                bundled_schema("debug-evidence-package.schema.json"),
            )
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"summary schema unavailable: {exc}")
    for field in ("dep_id", "issue", "risk_level", "workflow", "expected_behavior", "actual_behavior", "environment"):
        if field not in summary:
            errors.append(f"summary missing {field}")
    if (
        set(manifest) != {"schema_version", "dep_id", "raw", "shareable"}
        or manifest.get("schema_version") != "1.0"
    ):
        errors.append("manifest has an invalid root contract")
    if manifest.get("dep_id") != summary.get("dep_id"):
        errors.append("manifest dep_id does not match summary")
    phase = summary.get("workflow", {}).get("phase")
    if phase not in PHASES:
        errors.append("invalid workflow phase")
        return errors, summary, manifest, control_identities
    history = summary.get("workflow", {}).get("history")
    expected_history = list(PHASES[: PHASES.index(phase) + 1])
    actual_history = (
        [item.get("phase") for item in history if isinstance(item, dict)]
        if isinstance(history, list)
        else []
    )
    if actual_history != expected_history or not isinstance(history, list) or len(history) != len(expected_history):
        errors.append(
            "workflow history must be the exact phase prefix: " + " -> ".join(expected_history)
        )
    if strict and phase != "proof":
        errors.append(f"strict verification requires proof phase, found {phase}")
    for name in REQUIRED_DOCS["proof" if strict else phase]:
        try:
            document, _ = _read_regular_bytes_at(dep_fd, name, name)
        except FileNotFoundError:
            errors.append(f"missing {name}")
            continue
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if name.endswith(".md"):
            text = document.decode("utf-8", errors="ignore")
            meaningful = [
                line
                for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            if not any(
                "TODO" not in line and "<!--" not in line and "-->" not in line
                for line in meaningful
            ):
                errors.append(f"template not completed: {name}")
    if PHASES.index(phase) >= PHASES.index("evidence") or strict:
        if not manifest.get("raw"):
            errors.append("no collected evidence")
        try:
            report = _load_at(dep_fd, "redaction-report.json")
        except FileNotFoundError:
            report = None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid redaction report: {exc}")
            report = None
        if report is not None:
            if report.get("blocked"):
                errors.append("redaction report contains blocked artifacts requiring manual review")
            if not manifest.get("shareable"):
                errors.append("no shareable redacted evidence")
            errors.extend(
                _verify_redaction_associations(dep, dep_fd, manifest, report)
            )
        errors.extend(
            _verify_manifest_artifacts(
                dep, dep_fd, manifest, portable=portable
            )
        )
    raw_refs = [
        attachment
        for attachment in summary.get("attachments", [])
        if isinstance(attachment, dict)
        and str(attachment.get("path", "")).startswith("private/")
    ]
    if raw_refs:
        errors.append("summary attachments must never reference private/raw evidence")
    shareable_by_path = {
        row.get("path"): row
        for row in manifest.get("shareable", [])
        if isinstance(row, dict)
    }
    for attachment in summary.get("attachments", []):
        if not isinstance(attachment, dict):
            continue
        registered = shareable_by_path.get(attachment.get("path"))
        if registered is None or registered.get("sha256") != attachment.get("sha256"):
            errors.append("summary attachment is not bound to a matching shareable artifact")
    return errors, summary, manifest, control_identities


def _require_control_snapshot(
    dep_fd: int, identities: dict[str, tuple[int, int, int, int]]
) -> None:
    """Fail closed if a verified DEP control file was replaced before use."""
    for name in ("summary.yaml", "manifest.json"):
        try:
            metadata = os.stat(name, dir_fd=dep_fd, follow_symlinks=False)
        except OSError as exc:
            raise ValueError(f"verified control document changed: {name}") from exc
        observed = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
        )
        if not stat.S_ISREG(metadata.st_mode) or observed != identities.get(name):
            raise ValueError(f"verified control document changed: {name}")


def verify(dep: Path, strict: bool = False, portable: bool = False) -> list[str]:
    try:
        with _opened_dep_root(dep) as dep_fd:
            errors, _, _, _ = _verify_open(dep, dep_fd, strict, portable)
            return errors
    except (OSError, ValueError) as exc:
        return [f"Evidence filesystem boundary changed or is unsafe: {exc}"]


def attach(dep: Path, target: str, output: Path | None = None) -> Path:
    if target not in {"issue", "commit", "pr", "changelog"}:
        raise ValueError("target must be issue, commit, pr, or changelog")
    with _opened_dep_root(dep) as dep_fd:
        errors, summary, manifest, identities = _verify_open(
            dep, dep_fd, strict=True, portable=False
        )
        if errors:
            raise ValueError("DEP is not attachable: " + "; ".join(errors))
        if summary is None or manifest is None:
            raise ValueError("DEP verification did not return a control snapshot")
        lines = [
            f"Evidence: {summary['dep_id']}",
            f"Issue: {summary['issue']}",
            f"SDD: {', '.join(summary.get('sdd_references') or ['n/a'])}",
            f"Risk: {summary['risk_level']}",
            "Workflow: Red -> Evidence -> Fix -> Green -> Proof",
            "Verified artifacts:",
        ]
        lines.extend(
            f"- `{row['path']}` (sha256: `{row['sha256']}`)"
            for row in manifest.get("shareable", [])
        )
        lines.extend(["", f"Target: {target}"])
        encoded = ("\n".join(lines) + "\n").encode("utf-8")
        if output is None:
            name = f"attach-{target}.md"
            _attachment_write_transaction(
                dep_fd, dep_fd, name, encoded, identities
            )
            return dep / name
        with _opened_directory_path(output.parent, create=False) as (_, output_fd):
            _attachment_write_transaction(
                dep_fd, output_fd, output.name, encoded, identities
            )
        return output
