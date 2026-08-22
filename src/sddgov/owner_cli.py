"""Owner-only CLI for semantic approval through a separately held signer."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .owner_approval import (
    approve_product_decision,
    build_product_approval_card,
    product_approval_card_sha256,
    render_product_approval_card,
)


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
        with open("/dev/tty", "r+", encoding="utf-8", buffering=1) as terminal:
            terminal.write(rendered_card)
            terminal.write(f"Select one option ({'/'.join(sorted(labels))}): ")
            choice = terminal.readline().strip()
    except OSError as exc:
        raise ValueError(
            "Owner approval requires a controlling terminal; stdin and chat are not signing authority"
        ) from exc
    if choice not in labels:
        raise ValueError("Owner choice must name one displayed option")
    return choice


def _require_owner_runtime(repository_root: Path) -> None:
    """Reject candidate-checkout and Python-path injection signing contexts."""
    if any(name in os.environ for name in ("PYTHONPATH", "PYTHONHOME")):
        raise ValueError("Owner client requires PYTHONPATH and PYTHONHOME to be unset")
    executable = Path(sys.executable)
    invocation = Path(sys.argv[0])
    prefix = Path(sys.prefix).resolve()
    module = Path(__file__).resolve()
    if (
        sys.prefix == sys.base_prefix
        or not executable.is_absolute()
        or not invocation.is_absolute()
        or not invocation.resolve().is_relative_to(prefix)
        or not module.is_relative_to(prefix)
        or not executable.resolve().is_relative_to(prefix)
    ):
        raise ValueError(
            "Owner client must run by absolute path from an independently installed virtual environment"
        )
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
