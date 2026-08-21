from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .benchmark import compare
from .autonomy import (
    checkpoint,
    evaluate_deployment,
    evaluate_escalation,
    import_external_action_resolution,
    import_operation_approval,
    import_product_approval,
    lock_artifact,
    record_decision,
    verify_artifact,
)
from .ci_guard import run_local_gate, verify_guard
from .evidence import attach, collect, make_dep, redact, transition, verify
from .governance import claim_work, emit_event, enqueue_external_action, init_project, project_status
from .installer import AGENTS, _resource_files, doctor, setup_agent, uninstall_agent
from .merge_gate import (
    DEFAULT_GATE,
    compute_change_digest,
    compute_gate_metadata_digest,
    verify_merge,
)
from .pilot import run_quick_demo, run_synthetic_muse_pilot
from .broker import BROKER_SOCKET_GROUP, broker_readiness, serve_broker
from .reviewer import bootstrap_reviewer, export_trust, sign_protected_review
from .schema_validation import check_schema, load_schema, validate_instance


class SDGArgumentParser(argparse.ArgumentParser):
    """Keep parser failures distinct from validated owner decisions."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(3, f"{self.prog}: error: {message}\n")


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
    check.add_argument(
        "--portable",
        action="store_true",
        help="Verify a portable tracked DEP while allowing local-only raw files to be absent",
    )

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
    record = decision_commands.add_parser(
        "record", help="Deprecated unsafe L2 path; always fails closed"
    )
    record.add_argument("decision_id")
    record.add_argument("--summary", required=True)
    record.add_argument("--scope", required=True)
    record.add_argument("--basis", required=True)
    record.add_argument("--reopen-condition", required=True)
    record.add_argument("--path", type=Path, default=Path.cwd())
    import_product = decision_commands.add_parser(
        "import-product-approval",
        help="Verify and import one trusted owner-signed L2 product decision",
    )
    import_product.add_argument("receipt", type=Path)
    import_product.add_argument("--path", type=Path, default=Path.cwd())
    import_approval = decision_commands.add_parser(
        "import-operation-approval",
        help="Verify and import one trusted owner-signed L3 approval receipt",
    )
    import_approval.add_argument("receipt", type=Path)
    import_approval.add_argument("--path", type=Path, default=Path.cwd())

    report = subparsers.add_parser("checkpoint", help="Emit an informational checkpoint that continues by default")
    report.add_argument("--summary", required=True)
    report.add_argument("--next-work-package")

    deploy = subparsers.add_parser("deploy", help="Evaluate automated Production deployment guardrails")
    deploy_commands = deploy.add_subparsers(dest="deploy_command", required=True)
    deploy_evaluate = deploy_commands.add_parser("evaluate", help="Evaluate one JSON deployment gate")
    deploy_evaluate.add_argument("gate", type=Path)
    deploy_evaluate.add_argument("--path", type=Path, default=Path.cwd())


def build_parser() -> argparse.ArgumentParser:
    parser = SDGArgumentParser(prog="sddgov")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    broker = sub.add_parser("broker", help="Inspect or run the independent L3 nonce Broker")
    broker_commands = broker.add_subparsers(dest="broker_command", required=True)
    broker_doctor = broker_commands.add_parser(
        "doctor", help="Read-only readiness checks for L3 trust and Broker controls"
    )
    broker_doctor.add_argument("--path", type=Path, default=Path.cwd())
    broker_serve = broker_commands.add_parser(
        "serve", help="Run the root-owned Broker on the fixed platform socket"
    )
    broker_serve.add_argument("--socket-group", default=BROKER_SOCKET_GROUP)
    _evidence_parser(sub)
    _ci_parser(sub)
    _autonomy_parsers(sub)
    merge = sub.add_parser("merge", help="Enforce executable Merge policy gates")
    merge_commands = merge.add_subparsers(dest="merge_command", required=True)
    merge_digest = merge_commands.add_parser(
        "digest", help="Calculate the exact executable change digest for review receipts"
    )
    merge_digest.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    merge_digest.add_argument("--base-ref", required=True)
    merge_gate_digest = merge_commands.add_parser(
        "gate-digest", help="Calculate the review-bound Merge metadata digest"
    )
    merge_gate_digest.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    merge_gate_digest.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    merge_verify = merge_commands.add_parser(
        "verify", help="Verify exact change, Local Green, DEP, rollback, and review gates"
    )
    merge_verify.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    merge_verify.add_argument("--base-ref", required=True)
    merge_verify.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    merge_verify.add_argument(
        "--skip-local-checks",
        action="store_true",
        help="Do not execute candidate-defined Local Green commands (trusted hosted verifier only)",
    )
    reviewer = sub.add_parser(
        "reviewer", help="Provision and use an independent review identity"
    )
    reviewer_commands = reviewer.add_subparsers(dest="reviewer_command", required=True)
    reviewer_bootstrap = reviewer_commands.add_parser(
        "bootstrap",
        help="Create an external Ed25519 reviewer identity and public trust store",
    )
    reviewer_bootstrap.add_argument("--reviewer-id", required=True)
    reviewer_bootstrap.add_argument("--private-key", required=True, type=Path)
    reviewer_bootstrap.add_argument("--trust-file", required=True, type=Path)
    reviewer_bootstrap.add_argument("--path", type=Path, default=Path.cwd())
    reviewer_export = reviewer_commands.add_parser(
        "export-trust",
        help="Emit compact public-key JSON for a GitHub repository variable",
    )
    reviewer_export.add_argument("--trust-file", required=True, type=Path)
    reviewer_export.add_argument("--path", type=Path, default=Path.cwd())
    reviewer_sign = reviewer_commands.add_parser(
        "sign", help="Sign an independently reviewed exact Merge gate"
    )
    reviewer_sign.add_argument("--reviewer-id", required=True)
    reviewer_sign.add_argument("--private-key", required=True, type=Path)
    reviewer_sign.add_argument("--trust-file", required=True, type=Path)
    reviewer_sign.add_argument("--review-id", required=True)
    reviewer_sign.add_argument("--output", required=True, type=Path)
    reviewer_sign.add_argument("--base-ref", required=True)
    reviewer_sign.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    reviewer_sign.add_argument("--valid-hours", type=float, default=1.0)
    reviewer_sign.add_argument(
        "--approve-exact-change", action="store_true", required=True
    )
    reviewer_sign.add_argument("--path", type=Path, default=Path.cwd())
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
    external = sub.add_parser(
        "external-action", help="Queue or resolve one bounded owner action"
    )
    external_commands = external.add_subparsers(
        dest="external_action_command", required=True
    )
    external_queue = external_commands.add_parser(
        "queue", help="Queue one bounded Operational Action or Necessary UAT"
    )
    external_queue.add_argument("action_id")
    external_queue.add_argument("--summary", required=True)
    external_queue.add_argument("--risk", choices=("L1", "L2", "L3"), required=True)
    external_queue.add_argument("--owner", required=True)
    external_queue.add_argument("--scope", required=True)
    external_queue.add_argument(
        "--class",
        dest="action_class",
        choices=("operational_action", "necessary_uat"),
        default="operational_action",
    )
    external_queue.add_argument("--ttl-minutes", type=int, default=1440)
    external_queue.add_argument("--path", type=Path, default=Path.cwd())
    external_resolve = external_commands.add_parser(
        "resolve", help="Import one trusted owner-signed terminal resolution"
    )
    external_resolve.add_argument("receipt", type=Path)
    external_resolve.add_argument("--path", type=Path, default=Path.cwd())
    bench = sub.add_parser("benchmark", help="Compare paired debugging run results")
    bench_sub = bench.add_subparsers(dest="benchmark_command", required=True)
    cmp = bench_sub.add_parser("compare")
    cmp.add_argument("--screenshot", type=Path, required=True)
    cmp.add_argument("--evidence", type=Path, required=True)
    pilot = sub.add_parser("pilot", help="Run isolated synthetic adoption pilots")
    pilot_sub = pilot.add_subparsers(dest="pilot_command", required=True)
    synthetic_muse = pilot_sub.add_parser(
        "synthetic-muse", help="Run the offline synthetic Muse/Hermes pilot"
    )
    synthetic_muse.add_argument("--output", type=Path)
    quick_demo = pilot_sub.add_parser(
        "quick", help="Run the 30-second offline allow/block/evidence demo"
    )
    quick_demo.add_argument("--output", type=Path)
    validate = sub.add_parser("validate", help="Validate repository governance assets")
    validate.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    return parser


def _validate_repo(root: Path) -> list[str]:
    source_tree = (root / "pyproject.toml").is_file() and (
        root / "src/sddgov/cli.py"
    ).is_file()
    installed = root / ".agentic-sdd-governance"
    if not source_tree and installed.is_dir():
        root = installed

    managed_required = (
        "VERSION",
        "core/POLICY_KERNEL.md", "core/policy-kernel.yaml",
        "profiles/solo-fast.yaml", "profiles/team-standard.yaml", "profiles/regulated.yaml",
        "schemas/debug-evidence-package.schema.json", "schemas/collector-event.schema.json",
        "schemas/objective-contract.schema.json",
        "schemas/governance-event.schema.json", "schemas/work-claim.schema.json",
        "schemas/external-action.schema.json",
        "schemas/external-action-resolution-receipt.schema.json",
        "policies/protected-files.yaml",
        "schemas/autonomy-policy.schema.json", "schemas/decision-record.schema.json",
        "schemas/artifact-lock.schema.json", "policies/autonomy-policy.json",
        "schemas/trusted-approvers.schema.json", "schemas/operation-approval-receipt.schema.json",
        "schemas/product-decision-approval-receipt.schema.json",
        "schemas/trusted-reviewers.schema.json", "schemas/protected-review-receipt.schema.json",
        "schemas/merge-gate.schema.json",
        "schemas/ci-cost-guard.schema.json", "policies/ci-cost-guard.yaml",
        "docs/EVIDENCE_DRIVEN_SDD.md", "docs/CI_COST_GUARD.md",
        "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md", "templates/ACTION_REQUIRED.md",
        "docs/HARD_GATES_V1_2.md", "docs/L3_BROKER_OPERATIONS.md",
        "docs/OWNER_KEY_CEREMONY.md", "docs/ROLLBACK_OPERATIONS.md",
        "templates/EXTERNAL_ACTION_RESOLUTION_RECEIPT.json",
        "templates/PRODUCT_DECISION_APPROVAL_RECEIPT.json",
        "templates/CI_COST_GUARD.json",
        "services/com.sddgov.broker.plist", "services/sddgov-broker.service",
    )
    source_required = (
        "src/sddgov/merge_gate.py", "src/sddgov/reviewer.py",
        "src/sddgov/ci_guard.py",
        "src/sddgov/installer.py",
        "src/sddgov/broker.py",
        "src/sddgov/pilot.py",
        "src/sddgov/resources/governance/VERSION",
        "src/sddgov/resources/governance/skill/agentic-sdd-governance/SKILL.md",
        "skill/agentic-sdd-governance/SKILL.md",
        "skill/agentic-sdd-governance/references/ci-cost-guard.md",
        "skill/agentic-sdd-governance/references/independent-reviewer.md",
        "docs/AGENT_INSTALLATION.md", "CHANGELOG.md", "docs/ROADMAP.md",
    )
    required = (
        managed_required + source_required
        if source_tree
        else ("manifest.json",) + managed_required
    )
    errors = [f"missing {item}" for item in required if not (root / item).is_file()]
    if source_tree:
        try:
            embedded_assets = _resource_files()
        except (OSError, ValueError) as exc:
            errors.append(f"cannot inspect embedded governance assets: {exc}")
        else:
            for relative, embedded in embedded_assets.items():
                canonical = root / relative
                if not canonical.is_file():
                    errors.append(f"missing embedded governance source: {relative}")
                    continue
                try:
                    source = canonical.read_bytes()
                except OSError as exc:
                    errors.append(f"cannot read embedded governance source {relative}: {exc}")
                    continue
                if source != embedded:
                    errors.append(
                        f"embedded governance asset differs from source: {relative}"
                    )
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
    if args.command == "broker":
        if args.broker_command == "doctor":
            result = broker_readiness(args.path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 1
        if args.broker_command == "serve":
            serve_broker(args.socket_group)
            return 0
        raise ValueError(f"unknown broker command: {args.broker_command}")
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
        if args.external_action_command == "queue":
            result = enqueue_external_action(
                args.path,
                args.action_id,
                args.summary,
                args.risk,
                args.owner,
                scope=args.scope,
                ttl_minutes=args.ttl_minutes,
                action_class=args.action_class,
            )
        else:
            result = import_external_action_resolution(args.path, args.receipt)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "pilot":
        result = (
            run_synthetic_muse_pilot(args.output)
            if args.pilot_command == "synthetic-muse"
            else run_quick_demo(args.output)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["verdict"] == "PASS" else 1
    if args.command == "autonomy":
        try:
            request = json.loads(args.request.read_text(encoding="utf-8"))
            if not isinstance(request, dict):
                raise ValueError("autonomy request must be a JSON object")
            result = evaluate_escalation(args.path, request)
        except (OSError, TypeError, ValueError) as exc:
            result = {
                "state": "BLOCKED",
                "requires_response": False,
                "reason": "autonomy_request_has_an_invalid_contract",
                "detail": str(exc),
                "next_action": "repair_the_machine_request_before_reclassification",
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("state") == "CONTINUE":
            return 0
        if result.get("state") == "ACTION_REQUIRED":
            return 2
        return 1
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
        elif args.decision_command == "import-product-approval":
            result = import_product_approval(args.path, args.receipt)
        else:
            result = import_operation_approval(args.path, args.receipt)
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
    if args.command == "merge":
        if args.merge_command == "digest":
            result = compute_change_digest(args.path, args.base_ref)
        elif args.merge_command == "gate-digest":
            result = compute_gate_metadata_digest(args.path, args.gate)
        else:
            result = verify_merge(
                args.path,
                args.base_ref,
                args.gate,
                run_checks=not args.skip_local_checks,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 1
    if args.command == "reviewer":
        if args.reviewer_command == "bootstrap":
            result = bootstrap_reviewer(
                args.path, args.reviewer_id, args.private_key, args.trust_file
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.reviewer_command == "export-trust":
            print(export_trust(args.path, args.trust_file))
        else:
            result = sign_protected_review(
                args.path,
                args.reviewer_id,
                args.private_key,
                args.trust_file,
                args.review_id,
                args.output,
                base_ref=args.base_ref,
                gate_path=args.gate,
                valid_hours=args.valid_hours,
                approved=args.approve_exact_change,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate":
        errors = _validate_repo(args.path)
        if errors:
            print("\n".join(f"[ERROR] {e}" for e in errors), file=sys.stderr)
            return 1
        print("[OK] managed governance contracts and lifecycle assets")
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
        errors = verify(args.dep, args.strict, args.portable)
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
        raise SystemExit(3)


def evidence_main() -> None:
    argv = ["evidence", *sys.argv[1:]]
    try:
        raise SystemExit(run(build_parser().parse_args(argv)))
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()
