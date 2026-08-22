"""Owner-only CLI for semantic approval through a separately held signer."""

from __future__ import annotations

import argparse
import base64
import configparser
import csv
import hashlib
import importlib.metadata as importlib_metadata
import io
import os
import posixpath
import re
import site
import stat
import sys
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from .owner_approval import (
    approve_product_decision,
    build_product_approval_card,
    _existing_product_approval,
    _read_owner_client_source,
    _owner_client_identity,
    product_approval_card_sha256,
    render_product_approval_card,
)
from .fs_security import open_directory_path, require_directory_path_identity


OWNER_LAUNCHER_ENV = "SDDGOV_OWNER_ISOLATED_LAUNCHER"


def _record_sha256(raw: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode(
        "ascii"
    ).rstrip("=")


def _require_isolated_venv_config(raw: bytes) -> None:
    """Require one unambiguous system-site setting matching CPython venv policy."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Owner client pyvenv.cfg must be UTF-8") from exc
    entries: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=" not in line:
            raise ValueError("Owner client pyvenv.cfg contains a malformed setting")
        key, value = (part.strip() for part in line.split("=", 1))
        normalized_key = key.lower()
        if not normalized_key or normalized_key in entries:
            raise ValueError("Owner client pyvenv.cfg contains duplicate settings")
        entries[normalized_key] = value.lower()
    if entries.get("include-system-site-packages") != "false":
        raise ValueError("Owner client virtual environment must exclude system site packages")


def _require_isolated_runtime_paths() -> None:
    """Cross-check that Python did not activate user or base site packages."""
    if site.ENABLE_USER_SITE is not False:
        raise ValueError("Owner client Python user-site isolation is not active")
    try:
        base_sites = {
            Path(value).resolve()
            for value in site.getsitepackages([sys.base_prefix])
            if value
        }
    except (AttributeError, OSError) as exc:
        raise ValueError("Owner client base site-package paths are unavailable") from exc
    effective = {Path(value).resolve() for value in sys.path if value}
    if effective.intersection(base_sites):
        raise ValueError("Owner client virtual environment activated base site packages")


def _require_protected_owner_directory_chain(
    prefix: Path,
    target: Path,
    label: str,
) -> None:
    """Diagnose writable or ambiguous directories inside the Owner venv."""
    if not target.is_relative_to(prefix):
        raise ValueError(f"{label} is outside the Owner venv")
    current = prefix
    paths = [current]
    for part in target.relative_to(prefix).parts:
        current = current / part
        paths.append(current)
    for path in paths:
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise ValueError(f"{label} directory chain is unavailable") from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or (os.name != "nt" and metadata.st_uid != os.geteuid())
            or (os.name != "nt" and metadata.st_mode & 0o022)
        ):
            raise ValueError(f"{label} directory chain is not protected")


def _canonical_distribution_target(
    name: str,
    distribution_root: Path,
    prefix: Path,
    located: Path,
    allowed_external_rows: set[str],
) -> tuple[Path, tuple[int, int]]:
    """Resolve one canonical RECORD row without accepting alias spellings."""
    pure = PurePosixPath(name)
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or pure.is_absolute()
        or posixpath.normpath(name) != name
        or any(part in {"", "."} for part in pure.parts)
        or (".." in pure.parts and name not in allowed_external_rows)
    ):
        raise ValueError("Owner client distribution RECORD has a noncanonical path")
    lexical = Path(os.path.abspath(distribution_root.joinpath(*pure.parts)))
    if not lexical.is_relative_to(prefix):
        raise ValueError("Owner client distribution RECORD escapes the venv")
    try:
        metadata = lexical.lstat()
    except OSError as exc:
        raise ValueError("Owner client distribution RECORD target is unavailable") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (os.name != "nt" and metadata.st_uid != os.geteuid())
        or (os.name != "nt" and metadata.st_mode & 0o022)
    ):
        raise ValueError("Owner client distribution RECORD target is not a regular file")
    resolved = lexical.resolve()
    if resolved != Path(located).resolve() or not resolved.is_relative_to(prefix):
        raise ValueError("Owner client distribution RECORD target is ambiguous")
    return resolved, (metadata.st_dev, metadata.st_ino)


def _read_distribution_file(path: Path, label: str) -> bytes:
    directory_fd = open_directory_path(path.parent, label)
    try:
        raw = _read_owner_client_source(
            directory_fd,
            path.name,
            require_protected=True,
        )
        require_directory_path_identity(path.parent, directory_fd, label)
        return raw
    finally:
        closing_descriptor = directory_fd
        directory_fd = -1
        try:
            os.close(closing_descriptor)
        except OSError:
            pass


def _parse_exact_entry_points(raw: bytes) -> list[tuple[str, str, str]]:
    try:
        text = raw.decode("utf-8")
        parser = configparser.ConfigParser(
            interpolation=None,
            strict=True,
            delimiters=("=",),
        )
        parser.optionxform = str
        parser.read_string(text)
    except (UnicodeDecodeError, configparser.Error) as exc:
        raise ValueError("Owner client entry-point metadata is invalid") from exc
    if parser.sections() != ["console_scripts"]:
        raise ValueError("Owner client entry-point contract is invalid")
    return [
        ("console_scripts", name.strip(), value.strip())
        for name, value in parser.items("console_scripts")
    ]


def _require_owner_distribution(
    prefix: Path,
    module: Path,
    launcher: Path,
    expected_launcher: bytes,
) -> None:
    """Bind installed files, RECORD hashes, and entry points to the Owner client."""
    normalized_name = "agentic-sdd-governance"
    matches = []
    for candidate in importlib_metadata.distributions():
        candidate_name = candidate.metadata.get("Name", "")
        if re.sub(r"[-_.]+", "-", candidate_name).lower() == normalized_name:
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError("Owner client requires one unique installed distribution")
    distribution = matches[0]
    files = distribution.files
    if not files:
        raise ValueError("Owner client distribution RECORD is unavailable")
    client_identity = _owner_client_identity(require_protected=True)
    distribution_root = Path(distribution.locate_file("")).resolve()
    if (
        not distribution_root.is_relative_to(prefix)
        or module != distribution_root / "sddgov" / "owner_cli.py"
        or distribution.version != client_identity["version"]
    ):
        raise ValueError("Owner client distribution metadata is outside the venv")
    _require_protected_owner_directory_chain(
        prefix,
        distribution_root,
        "Owner client distribution",
    )
    external_targets = {
        prefix / "bin" / "evidence",
        prefix / "bin" / "sddgov",
        launcher,
    }
    allowed_external_rows = {
        PurePosixPath(os.path.relpath(target, distribution_root)).as_posix()
        for target in external_targets
    }
    by_name: dict[str, Any] = {}
    by_target: set[Path] = set()
    by_identity: set[tuple[int, int]] = set()
    checked_parents: set[Path] = set()
    for row in files:
        name = str(row)
        resolved, target_identity = _canonical_distribution_target(
            name,
            distribution_root,
            prefix,
            Path(row.locate()),
            allowed_external_rows,
        )
        if (
            name in by_name
            or resolved in by_target
            or target_identity in by_identity
        ):
            raise ValueError("Owner client distribution RECORD has duplicate targets")
        if resolved.parent not in checked_parents:
            _require_protected_owner_directory_chain(
                prefix,
                resolved.parent,
                "Owner client distribution target",
            )
            checked_parents.add(resolved.parent)
        by_name[name] = row
        by_target.add(resolved)
        by_identity.add(target_identity)
    actual_external_rows = {
        name for name in by_name if ".." in PurePosixPath(name).parts
    }
    if actual_external_rows != allowed_external_rows:
        raise ValueError("Owner client distribution external script rows differ")
    if len(by_name) != len(files):
        raise ValueError("Owner client distribution RECORD has duplicate paths")
    record_rows = [row for row in files if str(row).endswith(".dist-info/RECORD")]
    entry_point_rows = [
        row for row in files if str(row).endswith(".dist-info/entry_points.txt")
    ]
    if len(record_rows) != 1 or len(entry_point_rows) != 1:
        raise ValueError("Owner client distribution RECORD is outside the venv")
    record_parent = Path(record_rows[0].locate()).resolve().parent
    if (
        Path(entry_point_rows[0].locate()).resolve().parent != record_parent
        or record_parent.parent != distribution_root
    ):
        raise ValueError("Owner client distribution metadata roots differ")
    record_raw = _read_distribution_file(
        Path(record_rows[0].locate()).resolve(),
        "Owner client distribution RECORD",
    )
    try:
        record_table = list(
            csv.reader(
                io.StringIO(record_raw.decode("utf-8"), newline=""),
                strict=True,
            )
        )
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Owner client distribution RECORD is invalid") from exc
    if (
        len(record_table) != len(files)
        or any(len(row) != 3 for row in record_table)
        or [row[0] for row in record_table] != [str(row) for row in files]
    ):
        raise ValueError("Owner client distribution RECORD changed during validation")
    for metadata_row, raw_row in zip(files, record_table, strict=True):
        expected_hash = ""
        if metadata_row.hash is not None:
            expected_hash = f"{metadata_row.hash.mode}={metadata_row.hash.value}"
        expected_size = "" if metadata_row.size is None else str(metadata_row.size)
        if raw_row[1:] != [expected_hash, expected_size]:
            raise ValueError("Owner client distribution RECORD row is ambiguous")
        located = Path(metadata_row.locate()).resolve()
        if metadata_row.hash is not None:
            if metadata_row.hash.mode != "sha256":
                raise ValueError("Owner client distribution RECORD uses an unsupported hash")
            current_raw = _read_distribution_file(
                located,
                "Owner client distribution target",
            )
            if (
                _record_sha256(current_raw) != metadata_row.hash.value
                or (metadata_row.size is not None and len(current_raw) != metadata_row.size)
            ):
                raise ValueError("Owner client distribution target differs from RECORD")
    for source in client_identity["source_files"]:
        row = by_name.get(source["path"])
        if row is None or row.hash is None or row.hash.mode != "sha256":
            raise ValueError("Owner client source is not hash-bound by wheel RECORD")
        located = Path(row.locate()).resolve()
        if (
            not located.is_relative_to(prefix)
            or (source["path"] == "sddgov/owner_cli.py" and located != module)
            or row.hash.value
            != base64.urlsafe_b64encode(
                bytes.fromhex(source["sha256"])
            ).decode("ascii").rstrip("=")
        ):
            raise ValueError("Owner client source differs from wheel RECORD")
    launcher_rows = [
        row for row in files if Path(row.locate()).resolve() == launcher
    ]
    if (
        len(launcher_rows) != 1
        or launcher_rows[0].hash.value != _record_sha256(expected_launcher)
    ):
        raise ValueError("Owner isolated launcher is not hash-bound by wheel RECORD")
    entry_point_row = entry_point_rows[0]
    entry_point_raw = _read_distribution_file(
        Path(entry_point_row.locate()).resolve(),
        "Owner client entry-point metadata",
    )
    if (
        entry_point_row.hash is None
        or entry_point_row.hash.mode != "sha256"
        or entry_point_row.hash.value != _record_sha256(entry_point_raw)
    ):
        raise ValueError("Owner client entry-point metadata is not hash-bound by wheel RECORD")
    entry_points = _parse_exact_entry_points(entry_point_raw)
    if entry_points != [
        ("console_scripts", "evidence", "sddgov.cli:evidence_main"),
        ("console_scripts", "sddgov", "sddgov.cli:main"),
    ]:
        raise ValueError("Owner client distribution entry-point contract is invalid")


class OwnerArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        self.print_usage(sys.stderr)
        self.exit(3, f"{self.prog}: error: invalid bounded arguments\n")


def build_parser() -> argparse.ArgumentParser:
    parser = OwnerArgumentParser(
        prog="sddgov-owner",
        description=(
            "Owner-controlled approval client. Run only from a separately trusted "
            "terminal with an Agent-inaccessible Ed25519 Owner signer channel."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    approve = commands.add_parser(
        "approve-product",
        help="Approve or decline one displayed L2 option without editing a receipt",
    )
    approve.add_argument("request", help="Repository-relative L2 request JSON")
    approve.add_argument("--output", type=Path, required=True)
    approve.add_argument("--path", type=Path, default=Path.cwd())
    return parser


def _require_safe_cli_path(value: str | Path, label: str) -> None:
    raw = os.fspath(value)
    if (
        not raw
        or len(os.fsencode(raw)) > 4096
        or any(
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
            for character in raw
        )
    ):
        raise ValueError(f"{label} is invalid")


def run(args: argparse.Namespace) -> int:
    _request, card = build_product_approval_card(args.path, args.request)
    existing = _existing_product_approval(args.path, args.output, card)
    if existing is not None:
        _report_owner_outcome("APPROVED: the exact signed receipt was already committed.\n")
        return 0
    rendered_card = render_product_approval_card(card)
    choice = _read_owner_choice(card, rendered_card)
    result = approve_product_decision(
        args.path,
        args.request,
        choice,
        args.output,
        expected_card_sha256=product_approval_card_sha256(card),
    )
    if result["state"] == "APPROVED":
        _report_owner_outcome("APPROVED: the signed receipt is durably committed.\n")
        return 0
    _report_owner_outcome("DECLINED: no approval receipt was created.\n")
    return 1


def _report_owner_outcome(message: str) -> None:
    """Report after the transaction without turning display I/O into a retry signal."""
    try:
        with open("/dev/tty", "w", encoding="utf-8", buffering=1) as terminal:
            terminal.write(message)
            terminal.flush()
    except OSError:
        pass


def _read_owner_choice(card: dict[str, object], rendered_card: str) -> str:
    """Read the semantic choice only from the Owner's controlling terminal."""
    labels = {
        option["label"]
        for option in card["options"]
        if isinstance(option, dict) and isinstance(option.get("label"), str)
    }
    descriptor = -1
    raw_choice = b""
    try:
        descriptor = os.open(
            "/dev/tty",
            os.O_RDWR
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISCHR(metadata.st_mode) or not os.isatty(descriptor):
            raise ValueError("Owner approval requires a character controlling terminal")
        if os.tcgetpgrp(descriptor) != os.getpgrp():
            raise ValueError("Owner approval requires the foreground controlling terminal")
        prompt = (
            rendered_card + f"Select one option ({'/'.join(sorted(labels))}): "
        ).encode("utf-8")
        view = memoryview(prompt)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("Owner terminal write made no progress")
            view = view[written:]
        chunks: list[bytes] = []
        size = 0
        while size < 3:
            chunk = os.read(descriptor, 3 - size)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if b"\n" in chunk:
                break
        raw_choice = b"".join(chunks)
    except OSError as exc:
        raise ValueError(
            "Owner approval requires a controlling terminal; stdin and chat are not signing authority"
        ) from exc
    finally:
        if descriptor >= 0:
            closing_descriptor = descriptor
            descriptor = -1
            try:
                os.close(closing_descriptor)
            except OSError:
                # Once one exact choice line was read, close is resource cleanup;
                # it must not turn the semantic choice into a retryable prompt.
                pass
    if raw_choice not in {b"A\n", b"B\n"}:
        raise ValueError("Owner choice must be one bounded A or B line")
    choice = raw_choice[:1].decode("ascii")
    if choice not in labels:
        raise ValueError("Owner choice must name one displayed option")
    return choice


def _require_owner_runtime(repository_root: Path) -> None:
    """Reject candidate-checkout and Python-path injection signing contexts."""
    if not sys.flags.isolated:
        raise ValueError("Owner client requires the reviewed isolated launcher")
    if any(
        name in os.environ
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "PYTHONSTARTUP",
            "PYTHONINSPECT",
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
        )
    ):
        raise ValueError("Owner client rejects Python and dynamic-loader injection variables")
    executable = Path(sys.executable)
    prefix = Path(sys.prefix).resolve()
    module = Path(__file__).resolve()
    lexical_executable = Path(os.path.abspath(sys.executable))
    launcher_value = os.environ.get(OWNER_LAUNCHER_ENV, "")
    launcher = Path(launcher_value)
    expected_launcher = prefix / "bin" / "sddgov-owner"
    if (
        sys.prefix == sys.base_prefix
        or not executable.is_absolute()
        or not launcher.is_absolute()
        or launcher != expected_launcher
        or not module.is_relative_to(prefix)
        or not lexical_executable.is_relative_to(prefix)
    ):
        raise ValueError(
            "Owner client must run by absolute path from an independently installed virtual environment"
        )
    _require_protected_owner_directory_chain(
        prefix,
        module.parent,
        "Owner client package",
    )
    _require_protected_owner_directory_chain(
        prefix,
        launcher.parent,
        "Owner client launcher",
    )
    launcher_stat = launcher.lstat()
    if (
        not stat.S_ISREG(launcher_stat.st_mode)
        or launcher_stat.st_nlink != 1
        or (os.name != "nt" and launcher_stat.st_uid != os.geteuid())
        or launcher_stat.st_mode & 0o022
    ):
        raise ValueError("Owner isolated launcher is not a protected regular file")
    package_fd = -1
    launcher_fd = -1
    prefix_fd = -1
    try:
        package_fd = os.open(
            module.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        launcher_fd = os.open(
            launcher.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        prefix_fd = os.open(
            prefix,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        expected_bytes = _read_owner_client_source(
            package_fd,
            "owner_launcher.sh",
            require_protected=True,
        )
        installed_bytes = _read_owner_client_source(
            launcher_fd,
            launcher.name,
            require_protected=True,
        )
        venv_config = _read_owner_client_source(
            prefix_fd,
            "pyvenv.cfg",
            require_protected=True,
        )
    finally:
        for descriptor in (prefix_fd, launcher_fd, package_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
    if not hashlib.sha256(installed_bytes).digest() == hashlib.sha256(expected_bytes).digest():
        raise ValueError("Owner isolated launcher differs from the reviewed installed artifact")
    _require_isolated_venv_config(venv_config)
    _require_isolated_runtime_paths()
    _require_owner_distribution(prefix, module, launcher, expected_bytes)
    current = Path.cwd().resolve()
    repository = repository_root.resolve()
    if current == repository or current.is_relative_to(repository):
        raise ValueError("Owner client must start outside the Agent repository checkout")


def main() -> None:
    try:
        args = build_parser().parse_args()
        _require_safe_cli_path(args.request, "Owner request path")
        _require_safe_cli_path(args.output, "Owner receipt output path")
        _require_safe_cli_path(args.path, "Owner repository path")
        _require_owner_runtime(args.path)
        raise SystemExit(run(args))
    except (ValueError, OSError):
        print("[ERROR] Owner approval failed closed.", file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()
