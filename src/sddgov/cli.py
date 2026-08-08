from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .benchmark import compare
from .evidence import attach, collect, make_dep, redact, transition, verify
from .governance import claim_work, emit_event, enqueue_external_action, init_project, project_status


def _evidence_parser(subparsers) -> None:
    evidence = subparsers.add_parser("evidence", help="Manage Debug Evidence Packages")
    commands = evidence.add_subparsers(dest="evidence_command", required=True)

    init = commands.add_parser("init", help="Create a local DEP")
    init.add_argument("--issue", required=True)
    init.add_argument("--risk", default="L1", choices=("L0", "L1", "L2", "L3"))
    init.add_argument("--sdd")
    init.add_argument("--path", type=Path, default=Path("evidence"))
    init.add_argument("--id")

    capture = commands.add_parser("collect", help="Import collector output into private/raw")
    capture.add_argument("dep", type=Path)
    capture.add_argument("--collector", required=True)
    capture.add_argument("--input", type=Path, required=True)
    capture.add_argument("--label")

    clean = commands.add_parser("redact", help="Create locally redacted shareable artifacts")
    clean.add_argument("dep", type=Path)

    move = commands.add_parser("transition", help="Advance Red -> Evidence -> Fix -> Green -> Proof")
    move.add_argument("dep", type=Path)
    move.add_argument("phase", choices=("evidence", "fix", "green", "proof"))

    check = commands.add_parser("verify", help="Verify DEP structure and gates")
    check.add_argument("dep", type=Path)
    check.add_argument("--strict", action="store_true")

    link = commands.add_parser("attach", help="Generate a safe local evidence block")
    link.add_argument("dep", type=Path)
    link.add_argument("--target", required=True, choices=("issue", "commit", "pr", "changelog"))
    link.add_argument("--output", type=Path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sddgov")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    _evidence_parser(sub)
    init = sub.add_parser("init", help="Initialize project governance state")
    init.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    init.add_argument("--profile", choices=("solo-fast", "team-standard", "regulated"), default="team-standard")
    status = sub.add_parser("status", help="Show governance state")
    status.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    claim = sub.add_parser("claim", help="Claim a Work Package with a TTL")
    claim.add_argument("work_package")
    claim.add_argument("--agent", required=True)
    claim.add_argument("--ttl-minutes", type=int, default=60)
    claim.add_argument("--path", type=Path, default=Path.cwd())
    event = sub.add_parser("event", help="Append a governance telemetry event")
    event.add_argument("event_type")
    event.add_argument("--risk", choices=("L0", "L1", "L2", "L3"), required=True)
    event.add_argument("--payload", default="{}", help="JSON object")
    event.add_argument("--path", type=Path, default=Path.cwd())
    external = sub.add_parser("external-action", help="Queue one bounded owner action")
    external.add_argument("action_id")
    external.add_argument("--summary", required=True)
    external.add_argument("--risk", choices=("L2", "L3"), required=True)
    external.add_argument("--owner", required=True)
    external.add_argument("--path", type=Path, default=Path.cwd())
    bench = sub.add_parser("benchmark", help="Compare paired debugging run results")
    bench_sub = bench.add_subparsers(dest="benchmark_command", required=True)
    cmp = bench_sub.add_parser("compare")
    cmp.add_argument("--screenshot", type=Path, required=True)
    cmp.add_argument("--evidence", type=Path, required=True)
    validate = sub.add_parser("validate", help="Validate repository governance assets")
    validate.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    return parser


def _validate_repo(root: Path) -> list[str]:
    required = (
        "core/POLICY_KERNEL.md", "core/policy-kernel.yaml",
        "profiles/solo-fast.yaml", "profiles/team-standard.yaml", "profiles/regulated.yaml",
        "schemas/debug-evidence-package.schema.json", "schemas/objective-contract.schema.json",
        "schemas/governance-event.schema.json", "schemas/work-claim.schema.json",
        "schemas/external-action.schema.json", "policies/protected-files.yaml",
        "skill/agentic-sdd-governance/SKILL.md",
        "docs/EVIDENCE_DRIVEN_SDD.md", "CHANGELOG.md", "docs/ROADMAP.md",
    )
    errors = [f"missing {item}" for item in required if not (root / item).is_file()]
    skill = root / "skill/agentic-sdd-governance/SKILL.md"
    if skill.is_file() and len(skill.read_text(encoding="utf-8").splitlines()) > 500:
        errors.append("SKILL.md exceeds 500 lines")
    for schema in (root / "schemas").glob("*.json") if (root / "schemas").exists() else []:
        try:
            json.loads(schema.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON schema {schema.name}: {exc}")
    return errors


def run(args: argparse.Namespace) -> int:
    if args.command == "init":
        created = init_project(args.path, args.profile)
        print(json.dumps({"ok": True, "created": [str(p) for p in created]}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(project_status(args.path), ensure_ascii=False, indent=2))
        return 0
    if args.command == "claim":
        print(json.dumps(claim_work(args.path, args.work_package, args.agent, args.ttl_minutes), ensure_ascii=False, indent=2))
        return 0
    if args.command == "event":
        payload = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        print(json.dumps(emit_event(args.path, args.event_type, args.risk, payload), ensure_ascii=False, indent=2))
        return 0
    if args.command == "external-action":
        print(json.dumps(enqueue_external_action(args.path, args.action_id, args.summary, args.risk, args.owner), ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate":
        errors = _validate_repo(args.path)
        if errors:
            print("\n".join(f"[ERROR] {e}" for e in errors), file=sys.stderr)
            return 1
        print("[OK] governance kernel, profiles, evidence schema, skill, and lifecycle docs")
        return 0
    if args.command == "benchmark":
        print(json.dumps(compare(args.screenshot, args.evidence), ensure_ascii=False, indent=2))
        return 0
    if args.evidence_command == "init":
        print(make_dep(args.path, args.issue, args.risk, args.sdd, args.id))
    elif args.evidence_command == "collect":
        print(collect(args.dep, args.collector, args.input, args.label))
    elif args.evidence_command == "redact":
        print(json.dumps(redact(args.dep), ensure_ascii=False, indent=2))
    elif args.evidence_command == "transition":
        print(json.dumps(transition(args.dep, args.phase), ensure_ascii=False, indent=2))
    elif args.evidence_command == "verify":
        errors = verify(args.dep, args.strict)
        if errors:
            print("\n".join(f"[ERROR] {e}" for e in errors), file=sys.stderr)
            return 1
        print("[OK] Debug Evidence Package verified")
    elif args.evidence_command == "attach":
        print(attach(args.dep, args.target, args.output))
    return 0


def main() -> None:
    try:
        raise SystemExit(run(build_parser().parse_args()))
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)


def evidence_main() -> None:
    argv = ["evidence", *sys.argv[1:]]
    try:
        raise SystemExit(run(build_parser().parse_args(argv)))
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
