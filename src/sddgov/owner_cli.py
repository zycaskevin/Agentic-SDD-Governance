"""Owner-only CLI for semantic approval through a separately held signer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .owner_approval import (
    approve_product_decision,
    build_product_approval_card,
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
    show = commands.add_parser("show-product", help="Display one validated L2 approval card")
    show.add_argument("request", help="Repository-relative L2 request JSON")
    show.add_argument("--path", type=Path, default=Path.cwd())
    approve = commands.add_parser(
        "approve-product",
        help="Approve or decline one displayed L2 option without editing a receipt",
    )
    approve.add_argument("request", help="Repository-relative L2 request JSON")
    approve.add_argument("--assumption", action="append", required=True)
    approve.add_argument("--approver-id", required=True)
    approve.add_argument("--output", type=Path, required=True)
    approve.add_argument("--valid-days", type=int, default=30)
    approve.add_argument("--path", type=Path, default=Path.cwd())
    return parser


def run(args: argparse.Namespace) -> int:
    if args.command == "show-product":
        _request, card = build_product_approval_card(args.path, args.request)
        print(render_product_approval_card(card), end="")
        return 0
    _request, card = build_product_approval_card(args.path, args.request)
    print(render_product_approval_card(card), end="", flush=True)
    choice = _read_owner_choice(card)
    result = approve_product_decision(
        args.path,
        args.request,
        args.assumption,
        args.approver_id,
        choice,
        args.output,
        valid_days=args.valid_days,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "APPROVED" else 1


def _read_owner_choice(card: dict[str, object]) -> str:
    """Read the semantic choice only from the Owner's controlling terminal."""
    labels = {
        option["label"]
        for option in card["options"]
        if isinstance(option, dict) and isinstance(option.get("label"), str)
    }
    try:
        with open("/dev/tty", "r+", encoding="utf-8", buffering=1) as terminal:
            terminal.write(f"Select one option ({'/'.join(sorted(labels))}): ")
            choice = terminal.readline().strip()
    except OSError as exc:
        raise ValueError(
            "Owner approval requires a controlling terminal; stdin and chat are not signing authority"
        ) from exc
    if choice not in labels:
        raise ValueError("Owner choice must name one displayed option")
    return choice


def main() -> None:
    try:
        raise SystemExit(run(build_parser().parse_args()))
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()
