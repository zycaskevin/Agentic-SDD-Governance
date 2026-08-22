"""Owner-only CLI for semantic approval through a separately held signer."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata as importlib_metadata
import json
import os
import stat
import sys
from pathlib import Path

from .owner_approval import (
    approve_product_decision,
    build_product_approval_card,
    _read_owner_client_source,
    _owner_client_identity,
    product_approval_card_sha256,
    render_product_approval_card,
)


OWNER_LAUNCHER_ENV = "SDDGOV_OWNER_ISOLATED_LAUNCHER"


def _record_sha256(raw: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode(
        "ascii"
    ).rstrip("=")


def _require_owner_distribution(
    prefix: Path,
    module: Path,
    launcher: Path,
    expected_launcher: bytes,
) -> None:
    """Bind installed files, RECORD hashes, and entry points to the Owner client."""
    try:
        distribution = importlib_metadata.distribution("agentic-sdd-governance")
    except importlib_metadata.PackageNotFoundError as exc:
        raise ValueError("Owner client distribution metadata is unavailable") from exc
    files = distribution.files
    if not files:
        raise ValueError("Owner client distribution RECORD is unavailable")
    by_name = {str(row): row for row in files}
    if len(by_name) != len(files):
        raise ValueError("Owner client distribution RECORD has duplicate paths")
    record_rows = [row for row in files if str(row).endswith(".dist-info/RECORD")]
    if (
        len(record_rows) != 1
        or not Path(record_rows[0].locate()).resolve().is_relative_to(prefix)
    ):
        raise ValueError("Owner client distribution RECORD is outside the venv")
    identity = _owner_client_identity()
    for source in identity["source_files"]:
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
        row
        for row in files
        if row.hash is not None
        and row.hash.mode == "sha256"
        and Path(row.locate()).resolve() == launcher
    ]
    if (
        len(launcher_rows) != 1
        or launcher_rows[0].hash.value != _record_sha256(expected_launcher)
    ):
        raise ValueError("Owner isolated launcher is not hash-bound by wheel RECORD")
    entry_points = {
        (entry.group, entry.name, entry.value) for entry in distribution.entry_points
    }
    if entry_points != {
        ("console_scripts", "evidence", "sddgov.cli:evidence_main"),
        ("console_scripts", "sddgov", "sddgov.cli:main"),
    }:
        raise ValueError("Owner client distribution entry-point contract is invalid")


class OwnerArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(3, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = OwnerArgumentParser(
        prog="sddgov-owner",
        description=(
            "Owner-controlled approval client. Run only from a separately trusted "
            "terminal with a confirmation-constrained Ed25519 SSH agent."
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


def run(args: argparse.Namespace) -> int:
    _request, card = build_product_approval_card(args.path, args.request)
    rendered_card = render_product_approval_card(card)
    choice = _read_owner_choice(card, rendered_card)
    result = approve_product_decision(
        args.path,
        args.request,
        choice,
        args.output,
        expected_card_sha256=product_approval_card_sha256(card),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "APPROVED" else 1


def _read_owner_choice(card: dict[str, object], rendered_card: str) -> str:
    """Read the semantic choice only from the Owner's controlling terminal."""
    labels = {
        option["label"]
        for option in card["options"]
        if isinstance(option, dict) and isinstance(option.get("label"), str)
    }
    try:
        with (
            open("/dev/tty", "w", encoding="utf-8", buffering=1) as terminal_output,
            open("/dev/tty", "r", encoding="utf-8", buffering=1) as terminal_input,
        ):
            terminal_output.write(rendered_card)
            terminal_output.write(
                f"Select one option ({'/'.join(sorted(labels))}): "
            )
            terminal_output.flush()
            raw_choice = terminal_input.readline(3)
    except OSError as exc:
        raise ValueError(
            "Owner approval requires a controlling terminal; stdin and chat are not signing authority"
        ) from exc
    if raw_choice not in {"A\n", "B\n"}:
        raise ValueError("Owner choice must be one bounded A or B line")
    choice = raw_choice[0]
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
    launcher_stat = launcher.lstat()
    if (
        not stat.S_ISREG(launcher_stat.st_mode)
        or launcher_stat.st_nlink != 1
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
        expected_bytes = _read_owner_client_source(package_fd, "owner_launcher.sh")
        installed_bytes = _read_owner_client_source(launcher_fd, launcher.name)
        venv_config = _read_owner_client_source(prefix_fd, "pyvenv.cfg").decode(
            "utf-8"
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
    normalized_config = "\n".join(
        line.strip().lower() for line in venv_config.splitlines()
    )
    if "include-system-site-packages = false" not in normalized_config:
        raise ValueError("Owner client virtual environment must exclude system site packages")
    _require_owner_distribution(prefix, module, launcher, expected_bytes)
    current = Path.cwd().resolve()
    repository = repository_root.resolve()
    if current == repository or current.is_relative_to(repository):
        raise ValueError("Owner client must start outside the Agent repository checkout")


def main() -> None:
    try:
        args = build_parser().parse_args()
        _require_owner_runtime(args.path)
        raise SystemExit(run(args))
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()
