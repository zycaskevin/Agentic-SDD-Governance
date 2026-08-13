from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .benchmark import compare
from .autonomy import (
    authorize_operation,
    checkpoint,
    consume_operation_approval,
    evaluate_deployment,
    evaluate_escalation,
    lock_artifact,
    record_decision,
    verify_artifact,
)
from .ci_guard import run_local_gate, verify_guard
from .evidence import attach, collect, make_dep, redact, transition, verify
from .governance import claim_work, emit_event, enqueue_external_action, init_project, project_status
from .installer import AGENTS, doctor, setup_agent, uninstall_agent
from .schema_validation import check_schema, load_schema, validate_instance


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


def _ci_parser(subparsers) -> None:
    ci = subparsers.add_parser("ci", help="Enforce a repository CI Cost Guard")
    commands = ci.add_subparsers(dest="ci_command", required=True)
    check = commands.add_parser("verify", help="Verify CI budget contract and workflow controls")
    check.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    local = commands.add_parser("local-gate", help="Verify controls and run configured local Green checks")
    local.add_argument("path", nargs="?", type=Path, default=Path.cwd())


def _autonomy_parsers(subparsers) -> None:
    autonomy = subparsers.add_parser("autonomy", help="Classify escalation without unnecessary human prompts")
    autonomy_commands = autonomy.add_subparsers(dest="autonomy_command", required=True)
    evaluate = autonomy_commands.add_parser("evaluate", help="Evaluate one JSON escalation request")
    evaluate.add_argument("request", type=Path)
    evaluate.add_argument("--path", type=Path, default=Path.cwd())

    artifact = subparsers.add_parser("artifact", help="Generate and verify machine-readable artifact integrity locks")
    artifact_commands = artifact.add_subparsers(dest="artifact_command", required=True)
    lock = artifact_commands.add_parser("lock", help="Calculate SHA-256 and write release.lock")
    lock.add_argument("artifact", type=Path)
    lock.add_argument("--release", required=True)
    lock.add_argument("--output", type=Path, default=Path("release.lock"))
    verify_lock = artifact_commands.add_parser("verify", help="Recalculate and compare an artifact lock")
    verify_lock.add_argument("artifact", type=Path)
    verify_lock.add_argument("--lock", dest="lock_path", type=Path, default=Path("release.lock"))

    decision = subparsers.add_parser("decision", help="Record and reuse bounded L2/L3 decisions")
    decision_commands = decision.add_subparsers(dest="decision_command", required=True)
    record = decision_commands.add_parser("record", help="Record one approved L2 decision")
    record.add_argument("decision_id")
    record.add_argument("--summary", required=True)
    record.add_argument("--scope", required=True)
    record.add_argument("--basis", required=True)
    record.add_argument("--reopen-condition", required=True)
    record.add_argument("--path", type=Path, default=Path.cwd())
    authorize = decision_commands.add_parser("authorize-operation", help="Record fresh one-use approval for one concrete L3 operation")
    authorize.add_argument("approval_id")
    authorize.add_argument("--operation-id", required=True)
    authorize.add_argument("--summary", required=True)
    authorize.add_argument("--scope", required=True)
    authorize.add_argument("--approved-by", required=True)
    authorize.add_argument("--valid-minutes", type=int, default=60)
    authorize.add_argument("--path", type=Path, default=Path.cwd())
    consume = decision_commands.add_parser("consume-operation", help="Consume one exact L3 operation approval")
    consume.add_argument("approval_id")
    consume.add_argument("--operation-id", required=True)
    consume.add_argument("--path", type=Path, default=Path.cwd())

    report = subparsers.add_parser("checkpoint", help="Emit an informational checkpoint that continues by default")
    report.add_argument("--summary", required=True)
    report.add_argument("--next-work-package")

    deploy = subparsers.add_parser("deploy", help="Evaluate automated Production deployment guardrails")
    deploy_commands = deploy.add_subparsers(dest="deploy_command", required=True)
    deploy_evaluate = deploy_commands.add_parser("evaluate", help="Evaluate one JSON deployment gate")
    deploy_evaluate.add_argument("gate", type=Path)
    deploy_evaluate.add_argument("--path", type=Path, default=Path.cwd())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sddgov")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    _evidence_parser(sub)
    _ci_parser(sub)
    _autonomy_parsers(sub)
    init = sub.add_parser("init", help="Initialize project governance state")
    init.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    init.add_argument("--profile", choices=("solo-fast", "team-standard", "regulated"), default="team-standard")
    setup = sub.add_parser("setup-agent", help="Install governance and a discoverable Agent Skill")
    setup.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    setup.add_argument("--agent", choices=AGENTS, required=True)
    setup.add_argument("--profile", choices=("solo-fast", "team-standard", "regulated"), default="team-standard")
    setup.add_argument("--force", action="store_true", help="Replace only managed installation files after review")
    health = sub.add_parser("doctor", help="Verify an installed Agent governance integration")
    health.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    uninstall = sub.add_parser("uninstall-agent", help="Remove managed Agent integration files but retain state and evidence")
    uninstall.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    uninstall.add_argument("--force", action="store_true", help="Remove modified managed files after review")
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
        "schemas/debug-evidence-package.schema.json", "schemas/collector-event.schema.json",
        "schemas/objective-contract.schema.json",
        "schemas/governance-event.schema.json", "schemas/work-claim.schema.json",
        "schemas/external-action.schema.json", "policies/protected-files.yaml",
        "schemas/autonomy-policy.schema.json", "schemas/decision-record.schema.json",
        "schemas/artifact-lock.schema.json", "policies/autonomy-policy.json",
        "schemas/ci-cost-guard.schema.json", "policies/ci-cost-guard.yaml",
        "skill/agentic-sdd-governance/SKILL.md",
        "skill/agentic-sdd-governance/references/ci-cost-guard.md",
        "docs/EVIDENCE_DRIVEN_SDD.md", "docs/AGENT_INSTALLATION.md", "docs/CI_COST_GUARD.md",
        "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md", "templates/ACTION_REQUIRED.md",
        "templates/CI_COST_GUARD.json", "src/sddgov/ci_guard.py",
        "src/sddgov/installer.py",
        "src/sddgov/resources/governance/VERSION",
        "src/sddgov/resources/governance/skill/agentic-sdd-governance/SKILL.md",
        "CHANGELOG.md", "docs/ROADMAP.md",
    )
    errors = [f"missing {item}" for item in required if not (root / item).is_file()]
    skill = root / "skill/agentic-sdd-governance/SKILL.md"
    if skill.is_file() and len(skill.read_text(encoding="utf-8").splitlines()) > 500:
        errors.append("SKILL.md exceeds 500 lines")
    for schema in (root / "schemas").glob("*.json") if (root / "schemas").exists() else []:
        try:
            document = load_schema(schema)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid JSON schema {schema.name}: {exc}")
            continue
        errors.extend(f"invalid JSON schema {schema.name}: {error}" for error in check_schema(document))
    policy_path = root / "policies/autonomy-policy.json"
    policy_schema_path = root / "schemas/autonomy-policy.schema.json"
    if policy_path.is_file() and policy_schema_path.is_file():
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy_schema = load_schema(policy_schema_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid autonomy policy: {exc}")
        else:
            errors.extend(
                f"invalid autonomy policy: {error}"
                for error in validate_instance(policy, policy_schema)
            )
    return errors


def run(args: argparse.Namespace) -> int:
    if args.command == "init":
        created = init_project(args.path, args.profile)
        print(json.dumps({"ok": True, "created": [str(p) for p in created]}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(project_status(args.path), ensure_ascii=False, indent=2))
        return 0
    if args.command == "setup-agent":
        print(json.dumps(setup_agent(args.path, args.agent, args.profile, args.force), ensure_ascii=False, indent=2))
        return 0
    if args.command == "doctor":
        result = doctor(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.command == "uninstall-agent":
        print(json.dumps(uninstall_agent(args.path, args.force), ensure_ascii=False, indent=2))
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
    if args.command == "autonomy":
        request = json.loads(args.request.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise ValueError("autonomy request must be a JSON object")
        print(json.dumps(evaluate_escalation(args.path, request), ensure_ascii=False, indent=2))
        return 0
    if args.command == "artifact":
        if args.artifact_command == "lock":
            result = lock_artifact(args.artifact, args.release, args.output)
        else:
            result = verify_artifact(args.artifact, args.lock_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.command == "decision":
        if args.decision_command == "record":
            result = record_decision(
                args.path,
                args.decision_id,
                args.summary,
                args.scope,
                args.basis,
                args.reopen_condition,
            )
        elif args.decision_command == "authorize-operation":
            result = authorize_operation(
                args.path,
                args.approval_id,
                args.operation_id,
                args.summary,
                args.scope,
                args.approved_by,
                args.valid_minutes,
            )
        else:
            result = consume_operation_approval(
                args.path, args.approval_id, args.operation_id
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "checkpoint":
        print(json.dumps(checkpoint(args.summary, args.next_work_package), ensure_ascii=False, indent=2))
        return 0
    if args.command == "deploy":
        gate = json.loads(args.gate.read_text(encoding="utf-8"))
        if not isinstance(gate, dict):
            raise ValueError("deployment gate must be a JSON object")
        result = evaluate_deployment(args.path, gate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", result.get("state") == "CONTINUE") else 1
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
    if args.command == "ci":
        if args.ci_command == "verify":
            result = verify_guard(args.path)
        else:
            result = run_local_gate(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
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
