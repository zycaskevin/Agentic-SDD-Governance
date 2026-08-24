import json
import re
import unittest
from pathlib import Path
from pathlib import PurePosixPath
from unittest.mock import patch

import yaml

from sddgov import __version__, _require_supported_python
from sddgov.cli import _validate_repo
from sddgov.evidence import verify as verify_dep
from sddgov.installer import doctor
from sddgov.owner_approval import _owner_client_identity
from sddgov.redaction import (
    LOCAL_USER_PATH_PATTERN,
    MAX_LOGICAL_LINE_CHARACTERS,
    MAX_REDACTION_FILE_BYTES,
    STREAM_CHUNK_BYTES,
)
from sddgov.schema_validation import load_schema, validate_instance


ROOT = Path(__file__).resolve().parents[1]
WITHDRAWN_REDACTION_ERROR = re.compile(
    r"redaction report files\[(\d+)\] shareable output still matches redaction rules"
)


def _errors_are_exactly_withdrawn(
    dep: Path,
    errors: list[str],
    withdrawals: set[str],
) -> bool:
    """Allow only redaction failures bound to exact registered artifact paths."""
    try:
        report = json.loads((dep / "redaction-report.json").read_text(encoding="utf-8"))
        manifest = json.loads((dep / "manifest.json").read_text(encoding="utf-8"))
        report_files = report["files"]
        shareable_rows = manifest["shareable"]
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(report_files, list) or not isinstance(shareable_rows, list):
        return False
    manifest_paths = [
        row.get("path") for row in shareable_rows if isinstance(row, dict)
    ]
    for error in errors:
        match = WITHDRAWN_REDACTION_ERROR.fullmatch(error)
        if match is None:
            return False
        index = int(match.group(1))
        if index >= len(report_files) or not isinstance(report_files[index], dict):
            return False
        output = report_files[index].get("output")
        if not isinstance(output, str) or PurePosixPath(output).name != output:
            return False
        relative = PurePosixPath("shareable", "artifacts", output)
        if manifest_paths.count(relative.as_posix()) != 1:
            return False
        registered = PurePosixPath("evidence", dep.name, *relative.parts).as_posix()
        if registered not in withdrawals:
            return False
    return bool(errors)


class RepositoryContractTests(unittest.TestCase):
    def test_coderabbit_reviews_product_and_current_evidence_under_file_limit(self):
        configuration = yaml.safe_load(
            (ROOT / ".coderabbit.yaml").read_text(encoding="utf-8")
        )
        filters = configuration["reviews"]["path_filters"]
        expected_predecessors = {
            f"!evidence/DEP-RC1-REVIEW-FIX-R{revision}-{suffix}/**"
            for revision, suffix in (
                (6, "014"),
                (7, "015"),
                (8, "016"),
                (9, "017"),
                (10, "018"),
                (11, "019"),
                (12, "020"),
                (13, "021"),
                (14, "022"),
                (15, "023"),
                (16, "024"),
                (17, "025"),
                (18, "026"),
                (19, "027"),
                (20, "028"),
            )
        }
        self.assertEqual(set(filters), expected_predecessors)
        self.assertNotIn("!evidence/DEP-RC1-REVIEW-FIX-R21-029/**", filters)
        protected = yaml.safe_load(
            (ROOT / "policies/protected-files.yaml").read_text(encoding="utf-8")
        )
        self.assertIn(".coderabbit.yaml", protected["protected"])

    def test_repository_assets_validate(self):
        self.assertEqual(_validate_repo(ROOT), [])
        self.assertEqual(_validate_repo(ROOT / ".agentic-sdd-governance"), [])

    def test_source_validation_requires_runtime_and_owner_approval_modules(self):
        original = Path.is_file
        for missing in ("broker.py", "pilot.py", "owner_approval.py", "owner_cli.py"):
            with self.subTest(missing=missing), patch.object(
                Path,
                "is_file",
                autospec=True,
                side_effect=lambda path, *args, missing=missing, **kwargs: (
                    False
                    if path == ROOT / "src/sddgov" / missing
                    else original(path)
                ),
            ):
                self.assertIn(
                    f"missing src/sddgov/{missing}",
                    _validate_repo(ROOT),
                )

    def test_source_validation_checks_every_embedded_governance_asset(self):
        with patch("sddgov.cli.resource_files", return_value={"VERSION": b"tampered\n"}):
            errors = _validate_repo(ROOT)
        self.assertIn("embedded governance asset differs from source: VERSION", errors)

    def test_python_version_guard_has_an_actionable_error(self):
        with self.assertRaisesRegex(RuntimeError, "requires Python 3.10 or newer.*3.9"):
            _require_supported_python((3, 9))

    def test_english_readme_exposes_first_run_and_governance_tables(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "## Understand it in 30 seconds",
            "./demo/run.sh",
            "### Fast trial path",
            "### Controlled verified path",
            "### Contributor source path",
            "## What setup manages",
            "## Profiles",
            "## L0-L3 authority levels",
            "## Upgrade and uninstall",
            "## Known limitations",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)
        self.assertIn("| `solo-fast` |", readme)
        self.assertIn("| L3 |", readme)
        self.assertIn(f"agentic-sdd-governance=={__version__}", readme)
        self.assertNotIn('(cd sdg-release && rg "  $(basename', readme)
        self.assertIn('"$SDDGOV_BIN" setup-agent /absolute/path/to/project', readme)
        self.assertEqual(
            readme.count('SDDGOV_BIN="$(pwd)/.venv-sddgov/bin/sddgov"'), 2
        )
        self.assertIn("sddgov evidence init --issue", readme)
        controlled = readme.split("### Controlled verified path", 1)[1].split(
            "### Contributor source path", 1
        )[0]
        self.assertIn("sddgov pilot quick", controlled)
        for limit in ("10 MiB", "1,048,576", "64 KiB"):
            self.assertIn(limit, readme)
        self.assertIn("binary files fail closed", readme)
        self.assertIn("Native Windows may use that path only", readme)
        self.assertIn("use WSL2 for a full governed workflow", readme)

        demo = ROOT / "demo/run.sh"
        self.assertTrue(demo.is_file())
        self.assertNotEqual(demo.stat().st_mode & 0o111, 0)
        demo_text = demo.read_text(encoding="utf-8")
        self.assertIn("pilot quick", demo_text)
        self.assertIn("command -v python3", demo_text)
        self.assertIn('"PYTHONPATH=$repo_root/src"', demo_text)
        self.assertIn('"${sddgov_command[@]}" pilot quick', demo_text)
        self.assertIn('"$render_python" - "$demo_tmp/result.json"', demo_text)
        self.assertNotIn("\npython3 - \"$demo_tmp/result.json\"", demo_text)
        self.assertIn("trap 'on_signal 130' INT", demo_text)
        self.assertIn("trap 'on_signal 143' TERM", demo_text)
        pilot_text = (ROOT / "src/sddgov/pilot.py").read_text(encoding="utf-8")
        self.assertIn('"real_data_used": False', pilot_text)

    def test_fresh_wheel_smoke_does_not_import_the_source_checkout(self):
        smoke = ROOT / "scripts/fresh_wheel_smoke.py"
        self.assertTrue(smoke.is_file())
        text = smoke.read_text(encoding="utf-8")
        self.assertNotIn("PYTHONPATH=", text)
        self.assertNotIn('"-e"', text)
        self.assertIn('environment.pop("PYTHONPATH", None)', text)
        self.assertIn('if key.startswith("PIP_")', text)
        self.assertIn('for agent in ("codex", "hermes")', text)
        self.assertIn('"validate", str(project)', text)
        self.assertIn('"pilot", "quick"', text)
        self.assertIn('"source_checkout_imported": False', text)
        self.assertIn('"owner_approval_client": "PASS"', text)
        self.assertIn('"Scripts/sddgov-owner.exe"', text)
        self.assertIn("_snapshot_verified_bundle", text)
        self.assertIn("with _owner_install_umask():", text)
        self.assertIn('"-I",', text)
        self.assertIn("installed-wheel Owner diagnostics accepted an ambiguous", text)
        self.assertIn("installed-wheel Owner diagnostics accepted a group-writable", text)

    def test_skill_is_thin_and_routes_one_level_references(self):
        skill = ROOT / "skill/agentic-sdd-governance/SKILL.md"
        lines = skill.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 150)
        text = "\n".join(lines)
        self.assertIn("references/evidence-workflow.md", text)
        self.assertIn("references/autonomy-workflow.md", text)
        self.assertIn("references/independent-reviewer.md", text)
        self.assertIn("references/review-sharing.md", text)
        self.assertNotIn("# Evidence-Driven SDD", text)

    def test_json_schemas_are_parseable(self):
        for path in (ROOT / "schemas").glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_ci_permission_exception_schema_rejects_empty_job_maps(self):
        schema = json.loads(
            (ROOT / "schemas/ci-cost-guard.schema.json").read_text(encoding="utf-8")
        )
        exceptions = schema["properties"]["workflow_controls"]["properties"][
            "write_permission_exceptions"
        ]
        self.assertNotIn("minProperties", exceptions)
        self.assertEqual(exceptions["additionalProperties"]["minProperties"], 1)

    def test_dep_security_boundary_objects_reject_unknown_fields(self):
        schema = json.loads(
            (ROOT / "schemas/debug-evidence-package.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        history = schema["properties"]["workflow"]["properties"]["history"]
        self.assertEqual(history["minItems"], 1)
        self.assertEqual(history["maxItems"], 5)
        self.assertFalse(history["items"]["additionalProperties"])
        self.assertFalse(
            schema["properties"]["attachments"]["items"]["additionalProperties"]
        )

    def test_adapters_route_to_canonical_skill(self):
        codex = (ROOT / "adapters/codex/AGENTS.md").read_text(encoding="utf-8")
        hermes = (ROOT / "adapters/hermes/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("agentic-sdd-governance", codex)
        self.assertIn("agentic-sdd-governance", hermes)
        self.assertIn("Red -> Evidence -> Fix -> Green -> Proof", codex)
        self.assertIn("sddgov reviewer bootstrap", codex)
        self.assertIn("sddgov reviewer bootstrap", hermes)
        self.assertIn("references/review-sharing.md", codex)
        self.assertIn("references/review-sharing.md", hermes)
        self.assertIn("without asking the owner", codex)
        self.assertIn("without asking the owner", hermes)

    def test_packaged_hard_gate_assets_match_canonical_sources(self):
        paths = (
            "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md",
            "docs/CI_COST_GUARD.md",
            "docs/HARD_GATES_V1_2.md",
            "docs/L3_BROKER_OPERATIONS.md",
            "docs/OWNER_KEY_CEREMONY.md",
            "docs/ROLLBACK_OPERATIONS.md",
            "policies/autonomy-policy.json",
            "policies/protected-files.yaml",
            "schemas/autonomy-policy.schema.json",
            "schemas/ci-cost-guard.schema.json",
            "schemas/decision-record.schema.json",
            "schemas/external-action-resolution-receipt.schema.json",
            "schemas/external-action.schema.json",
            "schemas/merge-gate.schema.json",
            "schemas/operation-approval-receipt.schema.json",
            "schemas/runtime-context.schema.json",
            "schemas/product-decision-approval-receipt.schema.json",
            "schemas/protected-review-receipt.schema.json",
            "schemas/trusted-approvers.schema.json",
            "schemas/trusted-approver-domains.schema.json",
            "schemas/trusted-reviewers.schema.json",
            "services/sddgov-broker.service",
            "services/com.sddgov.broker.plist",
            "templates/MERGE_GATE.json",
            "templates/EXTERNAL_ACTION_RESOLUTION_RECEIPT.json",
            "templates/CI_COST_GUARD.json",
            "templates/OPERATION_APPROVAL_RECEIPT.json",
            "templates/L3_RUNTIME_CONTEXT.json",
            "templates/PRODUCT_DECISION_APPROVAL_RECEIPT.json",
            "templates/PROTECTED_REVIEW_RECEIPT.json",
            "templates/TRUSTED_APPROVERS.json",
            "templates/TRUSTED_APPROVER_DOMAINS.json",
            "templates/TRUSTED_REVIEWERS.json",
            "skill/agentic-sdd-governance/SKILL.md",
            "skill/agentic-sdd-governance/references/autonomy-workflow.md",
            "skill/agentic-sdd-governance/references/independent-reviewer.md",
            "skill/agentic-sdd-governance/references/review-sharing.md",
        )
        packaged = ROOT / "src/sddgov/resources/governance"
        for relative in paths:
            with self.subTest(path=relative):
                self.assertEqual(
                    (ROOT / relative).read_bytes(),
                    (packaged / relative).read_bytes(),
                )

    def test_current_repo_installed_governance_is_healthy_and_current(self):
        report = doctor(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["managed_file_count"], 73)

        triples = (
            (
                "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md",
                ".agentic-sdd-governance/docs/AUTONOMOUS_DEVELOPMENT_V1_2.md",
            ),
            (
                "docs/HARD_GATES_V1_2.md",
                ".agentic-sdd-governance/docs/HARD_GATES_V1_2.md",
            ),
            (
                "docs/L3_BROKER_OPERATIONS.md",
                ".agentic-sdd-governance/docs/L3_BROKER_OPERATIONS.md",
            ),
            (
                "docs/OWNER_KEY_CEREMONY.md",
                ".agentic-sdd-governance/docs/OWNER_KEY_CEREMONY.md",
            ),
            (
                "docs/ROLLBACK_OPERATIONS.md",
                ".agentic-sdd-governance/docs/ROLLBACK_OPERATIONS.md",
            ),
            (
                "policies/autonomy-policy.json",
                ".agentic-sdd-governance/policies/autonomy-policy.json",
            ),
            (
                "schemas/autonomy-policy.schema.json",
                ".agentic-sdd-governance/schemas/autonomy-policy.schema.json",
            ),
            (
                "schemas/external-action-resolution-receipt.schema.json",
                ".agentic-sdd-governance/schemas/external-action-resolution-receipt.schema.json",
            ),
            (
                "schemas/external-action.schema.json",
                ".agentic-sdd-governance/schemas/external-action.schema.json",
            ),
            (
                "templates/EXTERNAL_ACTION_RESOLUTION_RECEIPT.json",
                ".agentic-sdd-governance/templates/EXTERNAL_ACTION_RESOLUTION_RECEIPT.json",
            ),
            (
                "skill/agentic-sdd-governance/references/autonomy-workflow.md",
                ".agents/skills/agentic-sdd-governance/references/autonomy-workflow.md",
            ),
        )
        packaged = ROOT / "src/sddgov/resources/governance"
        for canonical_relative, installed_relative in triples:
            with self.subTest(path=canonical_relative):
                canonical = (ROOT / canonical_relative).read_bytes()
                self.assertEqual(canonical, (packaged / canonical_relative).read_bytes())
                self.assertEqual(canonical, (ROOT / installed_relative).read_bytes())

    def test_codex_adapter_preserves_repository_bootstrap_before_layered_loading(self):
        codex = (ROOT / "adapters/codex/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(
            "After completing the repository's required bootstrap reads, load only the following additional Governance Root sources:",
            codex,
        )

    def test_evidence_paths_are_normalized_and_zone_bounded(self):
        collector = json.loads(
            (ROOT / "schemas/collector-event.schema.json").read_text(encoding="utf-8")
        )
        attachment = json.loads(
            (ROOT / "schemas/debug-evidence-package.schema.json").read_text(encoding="utf-8")
        )
        collector_pattern = collector["properties"]["path"]["pattern"]
        attachment_pattern = attachment["properties"]["attachments"]["items"]["properties"]["path"]["pattern"]

        for pattern, accepted, rejected in (
            (
                collector_pattern,
                ["private/raw/terminal.log", "private/raw/run/output.json"],
                [
                    "private/raw/../shareable/leak.txt",
                    "private/raw/./log.txt",
                    "private/raw\\leak.txt",
                    "private/raw/control\u0000value.txt",
                    "private/raw/control\u001fvalue.txt",
                    "private/raw/control\u007fvalue.txt",
                    "private/raw/.. /leak.txt",
                    "private/raw/report. ",
                    "private/raw/report.",
                    "private/raw/",
                ],
            ),
            (
                attachment_pattern,
                ["shareable/artifacts/summary.txt", "shareable/artifacts/run/report.json"],
                [
                    "shareable/report.json",
                    "shareable/manifest.json",
                    "shareable/../private/raw.txt",
                    "shareable/./report.txt",
                    "shareable\\leak.txt",
                    "shareable/control\u0000value.txt",
                    "shareable/control\u001fvalue.txt",
                    "shareable/control\u007fvalue.txt",
                    "shareable/artifacts/.. /leak.txt",
                    "shareable/artifacts/report. ",
                    "shareable/artifacts/report.",
                    "shareable/",
                ],
            ),
        ):
            for value in accepted:
                self.assertIsNotNone(re.fullmatch(pattern, value), value)
            for value in rejected:
                self.assertIsNone(re.fullmatch(pattern, value), value)

    def test_objective_contract_lists_reject_blank_items(self):
        schema = json.loads(
            (ROOT / "schemas/objective-contract.schema.json").read_text(encoding="utf-8")
        )
        for key in ("guardrails", "keep_condition", "rollback_condition"):
            pattern = schema["properties"][key]["items"]["pattern"]
            self.assertIsNotNone(re.search(pattern, "bounded rollback"), key)
            self.assertIsNone(re.search(pattern, "   \t"), key)

    def test_redaction_inventory_matches_sensitive_identifier_contract(self):
        rules = json.loads((ROOT / "redaction/rules.json").read_text(encoding="utf-8"))
        actions = {item["id"]: item["action"] for item in rules["rules"]}
        self.assertEqual(actions["password"], "replace")
        self.assertEqual(actions["patient-identifier"], "mask")
        self.assertEqual(actions["customer-identifier"], "mask")
        self.assertEqual(actions["local-path"], "mask")
        self.assertEqual(MAX_REDACTION_FILE_BYTES, 10 * 1024 * 1024)
        self.assertEqual(MAX_LOGICAL_LINE_CHARACTERS, 1024 * 1024)
        self.assertEqual(STREAM_CHUNK_BYTES, 64 * 1024)
        redactor = (ROOT / "src/sddgov/redaction.py").read_text(encoding="utf-8")
        self.assertIn("unterminated private key block", redactor)
        gateway = (ROOT / "redaction/LOCAL_REDACTION_GATEWAY.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("1,048,576 decoded characters", gateway)

    def test_shareable_evidence_contains_no_absolute_user_workspace_paths(self):
        exposed = []
        for artifact in sorted(
            (ROOT / "evidence").glob("DEP-*/shareable/artifacts/**/*")
        ):
            if not artifact.is_file():
                continue
            try:
                text = artifact.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if LOCAL_USER_PATH_PATTERN.search(text):
                exposed.append(str(artifact.relative_to(ROOT)))
        exposed.sort()
        registry = json.loads(
            (ROOT / "evidence/shareable-artifact-withdrawals.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registry["schema_version"], "1.0")
        withdrawals = registry["withdrawals"]
        registered = [row["path"] for row in withdrawals]
        self.assertEqual(registered, sorted(set(registered)))
        self.assertEqual(exposed, registered)
        for row in withdrawals:
            self.assertEqual(row["status"], "withdrawn")
            self.assertEqual(row["reason"], "legacy-local-path-redaction-gap")
            replacement = ROOT / row["replacement"]
            self.assertTrue(replacement.is_file(), row)
            self.assertIsNone(
                LOCAL_USER_PATH_PATTERN.search(
                    replacement.read_text(encoding="utf-8")
                ),
                row,
            )

    def test_rc1_work_package_and_rollback_bind_current_proof(self):
        work_package = (ROOT / "work-packages/WP-RC1-READINESS-008.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "- Evidence: `DEP-RC1-STREAMING-REDACTION-R30-038` (authoritative)",
            work_package,
        )
        self.assertIn(
            "Complete and strictly verify `DEP-RC1-STREAMING-REDACTION-R30-038` at L2",
            work_package,
        )
        self.assertIn(
            "- Risk: L2 because R22 changes the public approver-authority source",
            work_package,
        )
        request = json.loads(
            (ROOT / "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            request["assumption_paths"],
            [
                "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.md",
                "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json",
            ],
        )
        decisions = json.loads(
            (ROOT / ".sddgov/decisions.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(decisions["decisions"]), 1)
        authority_decision = decisions["decisions"][0]
        self.assertEqual(
            authority_decision["decision_id"],
            "DEC-RC1-APPROVER-AUTHORITY-R22",
        )
        self.assertEqual(authority_decision["risk_level"], "L2")
        self.assertEqual(authority_decision["status"], "approved")
        self.assertEqual(
            authority_decision["reopen_condition"],
            "scope_or_assumptions_change",
        )
        self.assertEqual(
            authority_decision["assumptions"],
            [
                {
                    "path": "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.md",
                    "sha256": (
                        "8271356ba1d29478ccdeba6650e5c64f487ffea763b5918f117e5b04f45fa8ef"
                    ),
                },
                {
                    "path": "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json",
                    "sha256": (
                        "160a417a8388e73ae44236f36e62bd6a8adaeef6946f3386879bd946b54d551d"
                    ),
                },
            ],
        )
        rollback = (
            ROOT / "evidence/DEP-RC1-REVIEW-FIX-R6-014/rollback.md"
        ).read_text(encoding="utf-8")
        for required in (
            "sddgov.cli validate",
            "sddgov.cli doctor",
            "unittest discover -s tests -v",
            "python3 -m build --no-isolation",
            "python3 -m twine check",
            "scripts/fresh_wheel_smoke.py",
            "git diff --quiet",
        ):
            self.assertIn(required, rollback)

    def test_security_critical_sources_and_dependency_inputs_are_protected(self):
        policy = yaml.safe_load(
            (ROOT / "policies/protected-files.yaml").read_text(encoding="utf-8")
        )
        protected = set(policy["protected"])
        for required in (
            "src/sddgov/",
            ".github/workflows/",
            "AGENTS.md",
            ".gitignore",
            ".agents/",
            ".agentic-sdd-governance/",
            ".sddgov/project.json",
            ".sddgov/ci-cost-guard.json",
            "skill/",
            "adapters/",
            "pyproject.toml",
            "requirements-governance.lock",
            "requirements-release.in",
            "requirements-release.lock",
            "scripts/",
            "services/",
            "docs/HARD_GATES_V1_2.md",
            "docs/L3_BROKER_OPERATIONS.md",
            "docs/OWNER_KEY_CEREMONY.md",
            "docs/ROLLBACK_OPERATIONS.md",
        ):
            with self.subTest(required=required):
                self.assertIn(required, protected)

    def test_owner_key_and_broker_runbooks_cover_operational_failure_modes(self):
        key_runbook = (ROOT / "docs/OWNER_KEY_CEREMONY.md").read_text(encoding="utf-8")
        for required in (
            "different Ed25519 key",
            "Rotation",
            "Revocation and suspected compromise",
            "Loss recovery",
            "private key",
            "synthetic receipt",
            "Humans do not copy, calculate, compare, or approve digests",
            "/etc/sddgov/trusted-approvers.json",
            "SDDGOV_TRUSTED_APPROVERS_FILE",
            "separate privileged Operational/L3 action",
            "before the kernel starts the launcher",
            "diagnostic only",
        ):
            self.assertIn(required, key_runbook)
        self.assertNotIn("calculate its SHA-256 fingerprint", key_runbook)
        broker_runbook = (ROOT / "docs/L3_BROKER_OPERATIONS.md").read_text(encoding="utf-8")
        for required in (
            "sddgov broker doctor",
            "systemd",
            "WSL2",
            "launchd",
            "ALREADY_CONSUMED",
            "no production `--mock-broker`",
            "Ledger capacity and controlled epoch rollover",
            "parent directory when the ledger is first created",
            "SIGKILL",
            "Group=` value must remain identical",
        ):
            self.assertIn(required, broker_runbook)
        self.assertTrue((ROOT / "services/sddgov-broker.service").is_file())
        self.assertTrue((ROOT / "services/com.sddgov.broker.plist").is_file())
        self.assertIn("persistent control-plane files", broker_runbook)
        self.assertIn("socket group", broker_runbook)
        self.assertIn("0660", broker_runbook)

    def test_user_guide_preserves_red_evidence_before_returning_test_status(self):
        guide = (ROOT / "docs/USER_GUIDE.zh-TW.md").read_text(encoding="utf-8")
        collect_guard = guide.index('if [ "$collection_status" -ne 0 ]')
        redact = guide.index("sddgov evidence redact", collect_guard)
        transition = guide.index("sddgov evidence transition", redact)
        test_guard = guide.index('if [ "$test_status" -ne 0 ]', collect_guard)
        self.assertLess(collect_guard, redact)
        self.assertLess(redact, transition)
        self.assertLess(transition, test_guard)
        self.assertIn("sddgov evidence redact evidence/DEP-... || exit $?", guide)
        self.assertIn(
            "sddgov evidence transition evidence/DEP-... evidence || exit $?",
            guide,
        )

    def test_rollback_runbook_preserves_fail_closed_verifier_and_squash_mapping(self):
        runbook = (ROOT / "docs/ROLLBACK_OPERATIONS.md").read_text(encoding="utf-8")
        for required in (
            "single-parent",
            "one atomic implementation commit",
            "platform-generated squash SHA",
            "not the feature-branch SHA",
            "Break-glass incident recovery",
            "no `--skip-rollback`",
            "Never force push",
            "Within 24 hours",
            "Historical proof is not reusable authority",
            "previous gate fails its exact-Head check",
            "explicit L3 human approval",
            "every approver",
            "exact action and scope",
            "issue time",
            "expiry",
        ):
            self.assertIn(required, runbook)
        self.assertNotIn("sddgov merge verify --skip", runbook)
        guide = (ROOT / "docs/USER_GUIDE.zh-TW.md").read_text(encoding="utf-8")
        bug_section = guide[guide.index("## 6. Bug 與 Regression") :]
        self.assertLess(
            bug_section.index("`agentic-sdd-governance` Skill"),
            bug_section.index("### Red"),
        )

    def test_monorepo_benchmark_cannot_authorize_weaker_tree_proof(self):
        benchmark = (ROOT / "scripts/benchmark_monorepo_rollback.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"claim_allowed": False', benchmark)
        self.assertIn("retain full-tree proof; no affected-path optimization", benchmark)
        readme = (ROOT / "benchmarks/monorepo-rollback/README.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("p95 greater than 5 seconds", readme)
        self.assertIn("does not authorize", readme)
        self.assertIn("creates a new file exclusively", readme)
        self.assertNotIn(
            "--output benchmarks/monorepo-rollback/latest-result.json", readme
        )

    def test_monorepo_benchmark_uses_public_exact_tree_entry_point(self):
        benchmark = (ROOT / "scripts/benchmark_monorepo_rollback.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("rollback_ref_is_cleanly_revertible", benchmark)
        self.assertNotIn("_rollback_ref_is_cleanly_revertible", benchmark)

    def test_every_tracked_proof_dep_is_portable_strict(self):
        registry = json.loads(
            (ROOT / "evidence/shareable-artifact-withdrawals.json").read_text(
                encoding="utf-8"
            )
        )
        withdrawals = {row["path"] for row in registry["withdrawals"]}
        failures = {}
        for dep in sorted((ROOT / "evidence").glob("DEP-*")):
            summary = dep / "summary.yaml"
            if not summary.is_file():
                if {entry.name for entry in dep.iterdir()} == {"private"}:
                    continue
                failures[dep.name] = ["summary.yaml is required"]
                continue
            document = json.loads(summary.read_text(encoding="utf-8"))
            if document.get("workflow", {}).get("phase") != "proof":
                continue
            errors = verify_dep(dep, strict=True, portable=True)
            if errors and not _errors_are_exactly_withdrawn(
                dep, errors, withdrawals
            ):
                failures[dep.name] = errors
        self.assertEqual(failures, {})

    def test_withdrawal_exemption_is_bound_to_the_exact_report_artifact(self):
        dep = ROOT / "evidence/DEP-RC1-REVIEW-FIX-R10-018"
        report = json.loads(
            (dep / "redaction-report.json").read_text(encoding="utf-8")
        )
        registry = json.loads(
            (ROOT / "evidence/shareable-artifact-withdrawals.json").read_text(
                encoding="utf-8"
            )
        )
        withdrawals = {row["path"] for row in registry["withdrawals"]}
        withdrawn_index = next(
            index
            for index, row in enumerate(report["files"])
            if row["output"] == "terminal--r10-package-proof.txt"
        )
        unregistered_index = next(
            index
            for index, row in enumerate(report["files"])
            if row["output"] == "git--r10-git-context.txt"
        )
        self.assertTrue(
            _errors_are_exactly_withdrawn(
                dep,
                [
                    f"redaction report files[{withdrawn_index}] "
                    "shareable output still matches redaction rules"
                ],
                withdrawals,
            )
        )
        self.assertFalse(
            _errors_are_exactly_withdrawn(
                dep,
                [
                    f"redaction report files[{unregistered_index}] "
                    "shareable output still matches redaction rules"
                ],
                withdrawals,
            )
        )
        self.assertFalse(
            _errors_are_exactly_withdrawn(
                dep,
                [
                    "redaction report files[999] shareable output still "
                    "matches redaction rules"
                ],
                withdrawals,
            )
        )

    def test_terminal_external_action_schema_requires_signed_resolution_proof(self):
        schema = load_schema(ROOT / "schemas/external-action.schema.json")
        pending = {
            "action_id": "UAT-1",
            "summary": "one subjective UAT",
            "risk_level": "L1",
            "owner": "product-owner",
            "action_class": "necessary_uat",
            "scope": "uat:one-milestone",
            "status": "pending",
            "created_at": "2026-08-16T00:00:00Z",
            "expires_at": "2026-08-17T00:00:00Z",
            "request_sha256": "a" * 64,
            "authorization_scope": "one concrete action only",
        }
        self.assertEqual(validate_instance(pending, schema), [])
        terminal_without_proof = {**pending, "status": "completed"}
        self.assertTrue(validate_instance(terminal_without_proof, schema))

        terminal = {
            **terminal_without_proof,
            "resolved_at": "2026-08-16T01:00:00Z",
            "resolution_receipt_sha256": "b" * 64,
            "resolution_evidence_sha256": "c" * 64,
            "resolution_envelope": {
                "schema_version": "1.0",
                "algorithm": "ed25519",
                "receipt": {
                    "resolution_id": "RES-1",
                    "action_id": "UAT-1",
                    "action_class": "necessary_uat",
                    "owner": "product-owner",
                    "scope": "uat:one-milestone",
                    "request_sha256": "a" * 64,
                    "status": "completed",
                    "evidence_sha256": "c" * 64,
                    "resolved_at": "2026-08-16T01:00:00Z",
                    "expires_at": "2026-08-16T02:00:00Z",
                    "nonce": "resolution-nonce-1",
                },
                "signature": "A" * 88,
            },
        }
        self.assertEqual(validate_instance(terminal, schema), [])

    def test_rc1_uses_patched_cryptography_line(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        lock = (ROOT / "requirements-governance.lock").read_text(encoding="utf-8")
        self.assertIn('version = "0.2.0rc1"', pyproject)
        self.assertIn('cryptography>=50,<51', pyproject)
        self.assertNotIn('packaging>=26,<27', pyproject)
        self.assertIn("cryptography==50.0.0", lock)
        self.assertNotIn("packaging==26.3", lock)
        self.assertNotIn("cryptography==46.0.7", lock)

    def test_owner_approval_is_a_separate_non_key_cli_contract(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        agent_cli = (ROOT / "src/sddgov/cli.py").read_text(encoding="utf-8")
        owner_cli = (ROOT / "src/sddgov/owner_cli.py").read_text(encoding="utf-8")
        request = json.loads(
            (
                ROOT
                / "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json"
            ).read_text(encoding="utf-8")
        )
        self.assertIn('script-files = ["scripts/sddgov-owner"]', pyproject)
        self.assertNotIn('sddgov-owner = "sddgov.owner_cli:main"', pyproject)
        launcher = (ROOT / "scripts/sddgov-owner").read_bytes()
        self.assertEqual(
            launcher,
            (ROOT / "src/sddgov/owner_launcher.sh").read_bytes(),
        )
        self.assertIn(b'python" -I -m sddgov.owner_cli', launcher)
        self.assertIn('"show-product-approval"', agent_cli)
        self.assertNotIn('"approve-product"', agent_cli)
        self.assertIn('"approve-product"', owner_cli)
        self.assertNotIn("private-key", owner_cli)
        self.assertNotIn("signature", owner_cli)
        for source_path in (ROOT / "src/sddgov").glob("*.py"):
            if source_path.name in {"autonomy.py", "owner_approval.py"}:
                continue
            self.assertNotIn(
                "control_plane_loader=",
                source_path.read_text(encoding="utf-8"),
                source_path,
            )
        self.assertEqual(request["risk_level"], "L2")
        self.assertEqual(request["category"], "product_decision")
        self.assertEqual(
            request["decision_id"],
            "DEC-RC1-APPROVER-AUTHORITY-R22",
        )
        self.assertEqual(
            request["decision_scope"],
            request["decision_package"]["scope_of_approval"],
        )
        self.assertEqual(
            set(request["owner_client"]),
            {"version", "source_sha256"},
        )
        self.assertRegex(request["owner_client"]["source_sha256"], r"^[a-f0-9]{64}$")
        current_owner_client = _owner_client_identity()
        self.assertEqual(
            request["owner_client"],
            {
                "version": current_owner_client["version"],
                "source_sha256": current_owner_client["source_sha256"],
            },
        )
        decision_contract = (
            ROOT / "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.md"
        ).read_text(encoding="utf-8")
        expected_binding = "Owner client binding: " + json.dumps(
            request["owner_client"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(decision_contract.count(expected_binding), 1)

    def test_release_workflow_is_manual_isolated_and_attested(self):
        source = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
        # BaseLoader preserves workflow keys such as `on` as strings.
        workflow = yaml.load(source, Loader=yaml.BaseLoader)  # noqa: S506
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(
            set(workflow["jobs"]),
            {
                "require-release-tag",
                "build-and-smoke",
                "publish-testpypi",
                "verify-testpypi",
                "publish-github-release",
                "publish-pypi",
            },
        )
        for name, job in workflow["jobs"].items():
            permissions = job.get("permissions", {})
            if name in {"publish-testpypi", "publish-pypi"}:
                self.assertEqual(
                    permissions,
                    {"contents": "read", "id-token": "write"},
                )
                publish_steps = [step for step in job["steps"] if "pypi-publish@" in step.get("uses", "")]
                self.assertEqual(len(publish_steps), 1)
                self.assertEqual(publish_steps[0]["with"]["attestations"], "true")
            else:
                self.assertNotIn("id-token", permissions)
        self.assertNotIn("if", workflow["jobs"]["require-release-tag"])
        self.assertEqual(
            workflow["jobs"]["build-and-smoke"]["needs"], "require-release-tag"
        )
        self.assertEqual(workflow["jobs"]["publish-testpypi"]["needs"], "build-and-smoke")
        self.assertEqual(workflow["jobs"]["verify-testpypi"]["needs"], "publish-testpypi")
        for name in (
            "build-and-smoke",
            "publish-testpypi",
            "verify-testpypi",
            "publish-github-release",
        ):
            self.assertNotIn("if", workflow["jobs"][name])
        self.assertEqual(
            workflow["jobs"]["publish-pypi"]["needs"],
            ["verify-testpypi", "publish-github-release"],
        )
        self.assertIn("inputs.publish_pypi", workflow["jobs"]["publish-pypi"]["if"])
        self.assertEqual(workflow["jobs"]["publish-pypi"]["environment"]["name"], "pypi")
        for name in ("publish-testpypi", "publish-github-release", "publish-pypi"):
            job = workflow["jobs"][name]
            self.assertIn("environment", job)
            setup_steps = [
                step
                for step in job["steps"]
                if str(step.get("uses", "")).startswith("actions/setup-python@")
            ]
            self.assertEqual(len(setup_steps), 1, name)
            self.assertEqual(setup_steps[0]["with"]["python-version"], "3.12")
            token_steps = [
                step
                for step in job["steps"]
                if "RELEASE_CONFIGURATION_READ_TOKEN"
                in str(step.get("env", {}))
            ]
            self.assertEqual(len(token_steps), 1, name)
            self.assertIn('test "$GITHUB_REF_TYPE" = "tag"', token_steps[0]["run"])
        self.assertIn("test.pypi.org", source)
        self.assertIn('test "$GITHUB_REF_TYPE" = "tag"', source)
        self.assertIn('test "$GITHUB_REF_NAME" = "v$RELEASE_VERSION"', source)
        self.assertIn("fresh_wheel_smoke.py", source)
        self.assertIn("prepare_release_bundle.py", source)
        self.assertEqual(
            source.count(
                "PYTHONPATH=src python scripts/verify_release_assets.py release"
            ),
            4,
        )
        self.assertIn(
            "PYTHONPATH=src python scripts/prepare_release_bundle.py", source
        )
        self.assertGreaterEqual(
            source.count("PYTHONPATH=src python scripts/fresh_wheel_smoke.py"),
            2,
        )
        self.assertIn("check_release_environment.py", source)
        self.assertIn("RELEASE_CONFIGURATION_READ_TOKEN", source)
        self.assertIn("--bundle-root release/offline", source)
        self.assertIn('test "$(uname -m)" = "x86_64"', source)
        self.assertIn("--platform-label linux-x86_64-py312", source)
        self.assertIn("packages-dir: release/distributions", source)
        self.assertIn("--require-hashes -r requirements-release.lock", source)
        self.assertIn("--require-hashes -r requirements-governance.lock", source)
        self.assertIn("python -m venv .governance-venv", source)
        self.assertIn(
            "PYTHONPATH=src .governance-venv/bin/python -m unittest", source
        )
        validate_step = next(
            step
            for step in workflow["jobs"]["build-and-smoke"]["steps"]
            if step.get("name") == "Validate the source contracts"
        )
        validate_run = validate_step["run"]
        governance_install = (
            ".governance-venv/bin/python -m pip install --require-hashes "
            "-r requirements-governance.lock"
        )
        release_install = (
            ".governance-venv/bin/python -m pip install --require-hashes "
            "-r requirements-release.lock"
        )
        full_tests = "PYTHONPATH=src .governance-venv/bin/python -m unittest"
        self.assertIn(governance_install, validate_run)
        self.assertIn(release_install, validate_run)
        self.assertLess(
            validate_run.index(governance_install), validate_run.index(full_tests)
        )
        self.assertLess(validate_run.index(release_install), validate_run.index(full_tests))
        self.assertIn("for attempt in", source)
        self.assertIn("--no-cache-dir", source)
        self.assertIn("sleep 10", source)
        self.assertIn("Require byte equality with the built wheel", source)
        byte_equality_step = next(
            step
            for step in workflow["jobs"]["verify-testpypi"]["steps"]
            if step.get("name") == "Require byte equality with the built wheel"
        )
        self.assertEqual(byte_equality_step.get("env", {}).get("PYTHONPATH"), "src")
        self.assertNotIn("skip-existing", source)
        uses = re.findall(r"uses:\s*([^\s#]+)", source)
        self.assertTrue(uses)
        self.assertTrue(
            all(re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", value) for value in uses),
            uses,
        )
        guard = json.loads((ROOT / ".sddgov/ci-cost-guard.json").read_text(encoding="utf-8"))
        self.assertIn(
            [
                "python3",
                "-m",
                "sddgov.cli",
                "decision",
                "verify-product",
                "DEC-RC1-APPROVER-AUTHORITY-R22",
                "work-packages/DEC-RC1-APPROVER-AUTHORITY-R22.request.json",
                "--path",
                ".",
            ],
            guard["local_green"]["commands"],
        )
        self.assertEqual(guard["workflow_controls"]["exempt_workflows"], [])
        self.assertEqual(
            guard["workflow_controls"]["write_permission_exceptions"],
            {
                "publish.yml": {
                    "publish-testpypi": ["id-token"],
                    "publish-github-release": ["contents"],
                    "publish-pypi": ["id-token"],
                }
            },
        )

    def test_broker_service_unit_is_hardened(self):
        systemd = (ROOT / "services/sddgov-broker.service").read_text(
            encoding="utf-8"
        )
        directives = set(systemd.splitlines())
        for required in (
            "NoNewPrivileges=true",
            "PrivateDevices=true",
            "ProtectSystem=strict",
            "ProtectKernelTunables=true",
            "PrivateNetwork=true",
            "RestrictNamespaces=true",
            "ProtectProc=invisible",
            "RestrictRealtime=true",
            "MemoryDenyWriteExecute=true",
            "SystemCallArchitectures=native",
        ):
            with self.subTest(required=required):
                self.assertIn(required, systemd)
        for exact in ("CapabilityBoundingSet=", "RestrictAddressFamilies=AF_UNIX"):
            with self.subTest(exact=exact):
                self.assertIn(exact, directives)

        launchd = (ROOT / "services/com.sddgov.broker.plist").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "<key>ThrottleInterval</key>\n  <integer>30</integer>", launchd
        )
        self.assertIn("<key>GroupName</key>\n  <string>_sddgov</string>", launchd)
        self.assertIn("<key>Umask</key>\n  <integer>7</integer>", launchd)
        self.assertNotIn("StandardOutPath", launchd)
        self.assertNotIn("StandardErrorPath", launchd)
        self.assertIn("StartLimitIntervalSec=300", systemd)
        self.assertIn("StartLimitBurst=5", systemd)
        self.assertIn("RestartSec=30", systemd)

    def test_r6_hypothesis_records_falsification_results_before_confirmation(self):
        hypothesis = (
            ROOT / "evidence/DEP-RC1-REVIEW-FIX-R6-014/root-cause-hypothesis.md"
        ).read_text(encoding="utf-8")
        results = hypothesis.index("## Falsification results")
        conclusion = hypothesis.index("## Conclusion")
        self.assertLess(results, conclusion)
        self.assertIn("terminal--r6-red-tests.txt", hypothesis[results:conclusion])
        self.assertIn("terminal--r6-local-green.txt", hypothesis[results:conclusion])

    def test_r6_verification_does_not_claim_unattached_build_or_twine_proof(self):
        verification = (
            ROOT / "evidence/DEP-RC1-REVIEW-FIX-R6-014/verification.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("source build, Twine inspection", verification)
        self.assertNotIn("focused 113-test regression matrix", verification)

    def test_broker_service_mirrors_are_byte_identical(self):
        for name in (
            "sddgov-broker.service",
            "com.sddgov.broker.plist",
        ):
            canonical = (ROOT / "services" / name).read_bytes()
            for mirror in (
                ROOT / "src/sddgov/resources/governance/services" / name,
                ROOT / ".agentic-sdd-governance/services" / name,
            ):
                with self.subTest(name=name, mirror=mirror):
                    self.assertEqual(mirror.read_bytes(), canonical)

    def test_security_configuration_mirrors_are_byte_identical(self):
        for relative in (
            "schemas/ci-cost-guard.schema.json",
            "redaction/rules.json",
        ):
            canonical = (ROOT / relative).read_bytes()
            for prefix in (
                ROOT / "src/sddgov/resources/governance",
                ROOT / ".agentic-sdd-governance",
            ):
                with self.subTest(relative=relative, prefix=prefix):
                    self.assertEqual((prefix / relative).read_bytes(), canonical)

    def test_release_tool_lock_excludes_reviewed_vulnerable_ranges(self):
        requirements = (ROOT / "requirements-release.in").read_text(
            encoding="utf-8"
        )
        lock = (ROOT / "requirements-release.lock").read_text(encoding="utf-8")
        self.assertIn("setuptools>=83,<84", requirements)
        self.assertIn("wheel>=0.46.2,<1", requirements)
        self.assertRegex(lock, r"(?m)^setuptools==83\.0\.0 \\")
        self.assertRegex(lock, r"(?m)^wheel==0\.48\.0 \\")

    def test_offline_install_examples_guard_platform_before_download(self):
        for relative in ("README.md", "README.zh-TW.md", "docs/USER_GUIDE.zh-TW.md"):
            with self.subTest(relative=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                download = text.index("gh release download v0.2.0rc1")
                linux = text.rindex('test "$(uname -s)" = "Linux"', 0, download)
                architecture = text.rindex(
                    'test "$(uname -m)" = "x86_64"', 0, download
                )
                self.assertLess(linux, download)
                self.assertLess(architecture, download)

    def test_l3_runbook_pins_authority_and_validates_launchd_assets(self):
        runbook = (ROOT / "docs/L3_BROKER_OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn(
            "fixed paths `/etc/sddgov/trusted-approvers.json` and "
            "`/etc/sddgov/trusted-approver-domains.json`",
            runbook,
        )
        self.assertNotIn("export SDDGOV_TRUSTED_APPROVERS_FILE", runbook)
        self.assertIn("test -x /opt/sddgov/venv/bin/sddgov", runbook)
        self.assertNotIn("newsyslog", runbook)
        self.assertIn("unified system log", runbook)
        self.assertIn("never logs request bytes", runbook)
        self.assertIn("`root:sddgov` mode `0640`", runbook)
        self.assertIn("Mode `0600` is not valid", runbook)
        self.assertIn("clock-safety interval is five minutes", runbook)
        self.assertIn("latest `expires_at`", runbook)

    def test_runtime_uses_public_resource_accessor(self):
        installer = (ROOT / "src/sddgov/installer.py").read_text(encoding="utf-8")
        cli = (ROOT / "src/sddgov/cli.py").read_text(encoding="utf-8")
        self.assertIn("def resource_files()", installer)
        self.assertNotIn("_resource_files", cli)

    def test_historical_rollback_procedures_are_inert_and_verify_release_tools(self):
        for dep in (
            "DEP-RC1-REVIEW-FIX-R10-018",
            "DEP-RC1-REVIEW-FIX-R11-019",
        ):
            with self.subTest(dep=dep):
                text = (ROOT / "evidence" / dep / "rollback.md").read_text(
                    encoding="utf-8"
                )
                self.assertNotRegex(text, r"(?m)^# (?:git diff|test -z)")
                self.assertIn("WARNING: git revert changes the isolated checkout", text)
                self.assertIn("RELEASE_PYTHON", text)
                self.assertIn('"$RELEASE_PYTHON" -m pip check', text)

    def test_rollback_runbook_fetches_live_protected_branch(self):
        runbook = (ROOT / "docs/ROLLBACK_OPERATIONS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'protected_branch="${SDDGOV_PROTECTED_BRANCH:?set the protected branch}"',
            runbook,
        )
        fetch = runbook.index('git fetch --prune origin "$protected_branch"')
        branch = runbook.index(
            'git switch -c incident/INC-YYYY-NNN "origin/$protected_branch"'
        )
        self.assertLess(fetch, branch)

    def test_collector_playbooks_preserve_safe_reproduction_context(self):
        browser = (ROOT / "collectors/browser-playwright.md").read_text(encoding="utf-8")
        terminal = (ROOT / "collectors/terminal-git.md").read_text(encoding="utf-8")
        self.assertIn("URL fragments", browser)
        self.assertIn("failing-test-context.txt", terminal)
        self.assertIn("exit status", terminal)

    def test_coderabbit_upstream_review_contracts(self):
        contracts = {
            "browser deny-by-default URL handling": (
                ROOT / "collectors/browser-playwright.md",
                (
                    "Deny by default",
                    "query parameters",
                    "path segments",
                    "headers",
                    "referrers",
                    "Supabase service-role",
                    "safe metadata allowlist",
                    "Referer",
                    "Set-Cookie",
                    "Proxy-Authorization",
                    "API-key",
                ),
            ),
            "bounded Flutter capture": (
                ROOT / "collectors/flutter-android.md",
                ("Press `q`", "wait until `flutter run` exits", "<DEP>/private/raw/flutter-failure.log"),
            ),
            "bounded Android capture": (
                ROOT / "collectors/flutter-android.md",
                ("Press Ctrl-C", "wait until `adb logcat` exits", "<DEP>/private/raw/logcat-failure.log"),
            ),
            "terminal private evidence and collection status": (
                ROOT / "collectors/terminal-git.md",
                (
                    "<DEP>/private/raw/failing-test.log",
                    "<DEP>/private/raw/failing-test-context.txt",
                    "collection_status",
                ),
            ),
            "Supabase and Docker private evidence": (
                ROOT / "collectors/supabase-docker.md",
                (
                    "<DEP>/private/raw/supabase-function.log",
                    "<DEP>/private/raw/docker-failure.log",
                ),
            ),
            "repository-relative Cost Guard template": (
                ROOT / "docs/CI_COST_GUARD.md",
                (".agentic-sdd-governance/templates/CI_COST_GUARD.json",),
            ),
            "explicit DEP verification command": (
                ROOT / "docs/EVIDENCE_DRIVEN_SDD.md",
                ("evidence verify <DEP> --strict",),
            ),
            "explicit DEP verification command in Skill": (
                ROOT / "skill/agentic-sdd-governance/SKILL.md",
                ("evidence verify <DEP> --strict",),
            ),
            "rejected Issue root-cause state": (
                ROOT / "templates/ISSUE_EVIDENCE.md",
                ("unknown / hypothesized / confirmed / rejected",),
            ),
            "destination-authorized attachment": (
                ROOT / "skill/agentic-sdd-governance/references/dep-contract.md",
                ("approved package state", "Decision Package", "explicit approval", "authorized destination", "minimum disclosure"),
            ),
            "narrow L2 trigger": (
                ROOT / "skill/agentic-sdd-governance/references/evidence-workflow.md",
                ("approved behavior", "user-visible promises", "authority boundaries", "ordinary bug fix"),
            ),
            "unambiguous regression level": (
                ROOT / "skill/agentic-sdd-governance/references/risk-evidence-matrix.md",
                ("Every regression fix is L1", "full DEP"),
            ),
        }
        for label, (path, fragments) in contracts.items():
            with self.subTest(contract=label):
                text = path.read_text(encoding="utf-8")
                for fragment in fragments:
                    self.assertIn(fragment, text)

    def test_autonomy_v1_2_contract_is_machine_enforced(self):
        policy = json.loads(
            (ROOT / "policies/autonomy-policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual(policy["default_state"], "CONTINUE")
        self.assertTrue(policy["no_human_escalation_if_machine_verifiable"])
        self.assertEqual(policy["action_classifier"]["unknown_category_state"], "BLOCKED")
        self.assertTrue(policy["action_classifier"]["sensitive_effects_require_l3"])
        self.assertEqual(policy["approval_budget"]["L0"], 0)
        self.assertEqual(policy["approval_budget"]["L1"], 0)
        self.assertTrue(policy["integrity"]["human_copy_paste_forbidden"])
        self.assertFalse(policy["integrity"]["mismatch_requires_human_approval"])
        self.assertEqual(policy["classifier_exit_codes"]["PROCESS_ERROR"], 3)
        self.assertTrue(
            policy["external_action_lifecycle"][
                "necessary_uat_requires_subjective_judgment"
            ]
        )
        self.assertTrue(
            policy["external_action_lifecycle"][
                "machine_verifiable_work_must_be_reclassified"
            ]
        )
        routine_review = policy["routine_external_review"]
        self.assertTrue(routine_review["pre_authorized"])
        self.assertFalse(routine_review["owner_response_required"])
        self.assertTrue(routine_review["reviewer_must_be_preconfigured"])
        self.assertEqual(
            routine_review["default_public_payload"],
            ["committed_pull_request_diff", "public_repository_instructions"],
        )
        self.assertTrue(
            routine_review["public_repository_required_for_pre_authorization"]
        )
        self.assertTrue(
            routine_review[
                "private_repository_requires_separate_recorded_pair_authorization"
            ]
        )
        self.assertEqual(
            set(routine_review["forbidden_payloads"]),
            {
                "secrets",
                "credentials",
                "raw_evidence",
                "unredacted_sensitive_material",
                "production_dumps",
                "real_user_data",
            },
        )
        self.assertTrue(routine_review["review_output_is_untrusted"])
        self.assertTrue(routine_review["signed_independent_review_still_required"])
        self.assertTrue(
            routine_review["new_vendor_or_destination_requires_escalation"]
        )
        self.assertTrue(routine_review["new_access_requires_operational_action"])
        self.assertTrue(routine_review["new_cost_requires_owner_decision"])
        self.assertFalse(policy["l3_approval_receipts"]["caller_strings_are_authority"])
        self.assertFalse(
            policy["l3_approval_receipts"]["candidate_worktree_store_is_authority"]
        )
        self.assertTrue(policy["l3_approval_receipts"]["consume_atomically_on_continue"])
        self.assertFalse(policy["production_deploy"]["l0_pre_authorized"])
        self.assertFalse(policy["production_deploy"]["l1_pre_authorized"])
        self.assertTrue(
            policy["production_deploy"][
                "l1_autonomous_with_recorded_baseline_authorization"
            ]
        )
        kernel = (ROOT / "core/POLICY_KERNEL.md").read_text(encoding="utf-8")
        self.assertIn("NO_HUMAN_ESCALATION_IF_MACHINE_VERIFIABLE", kernel)
        self.assertIn("AUTOMATIC_REVIEW_IS_PREAUTHORIZED", kernel)
        self.assertIn("Never ask a human to copy, paste", kernel)
        autonomy = (ROOT / "docs/AUTONOMOUS_DEVELOPMENT_V1_2.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("AUTONOMY BY DEFAULT. ESCALATION BY EXCEPTION.", autonomy)
        self.assertIn("AUTOMATIC_REVIEW_IS_PREAUTHORIZED", autonomy)
        self.assertIn("Main Agent", autonomy)
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/governance.yml").read_text(encoding="utf-8")
        )
        verifier_jobs = [
            job
            for job in workflow["jobs"].values()
            if any(
                "merge verify" in str(step.get("run", ""))
                for step in job.get("steps", [])
            )
        ]
        self.assertEqual(len(verifier_jobs), 1)
        verifier_steps = [
            step
            for step in verifier_jobs[0]["steps"]
            if "merge verify" in str(step.get("run", ""))
        ]
        self.assertEqual(len(verifier_steps), 1)
        self.assertIn(
            "SDDGOV_TRUSTED_REVIEWERS_JSON", verifier_steps[0].get("env", {})
        )
        self.assertIn(
            "SDDGOV_TRUSTED_REVIEWERS_FILE", verifier_steps[0].get("env", {})
        )
        checkout_steps = [
            step
            for step in verifier_jobs[0]["steps"]
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        self.assertEqual(len(checkout_steps), 2)
        by_path = {step["with"]["path"]: step for step in checkout_steps}
        self.assertEqual(set(by_path), {"candidate", "trusted-verifier"})
        self.assertEqual(by_path["candidate"]["with"]["fetch-depth"], 0)
        self.assertFalse(by_path["candidate"]["with"]["persist-credentials"])
        self.assertIn(
            "pull_request.head.sha", by_path["candidate"]["with"]["ref"]
        )
        self.assertIn(
            "pull_request.base.sha", by_path["trusted-verifier"]["with"]["ref"]
        )
        workflow_events = workflow[True]
        self.assertIn("pull_request_target", workflow_events)
        self.assertIn("workflow_dispatch", workflow_events)
        self.assertNotIn("push", workflow_events)
        cli = (ROOT / "src/sddgov/cli.py").read_text(encoding="utf-8")
        self.assertIn("import-product-approval", cli)
        self.assertIn("import-operation-approval", cli)
        self.assertNotIn('"authorize-operation"', cli)
        all_runtime_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "core/POLICY_KERNEL.md",
                ROOT / "core/policy-kernel.yaml",
                ROOT / "policies/autonomy-policy.json",
                ROOT / "skill/agentic-sdd-governance/SKILL.md",
                ROOT / "src/sddgov/autonomy.py",
            )
        ).lower()
        self.assertNotIn("paste sha-256 to approve", all_runtime_text)
        self.assertNotIn("貼回 sha-256", all_runtime_text)

    def test_pull_request_gate_uses_base_trusted_verifier(self):
        workflow = (ROOT / ".github/workflows/governance.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("path: candidate", workflow)
        self.assertIn("path: trusted-verifier", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("PYTHONPATH", workflow)
        self.assertIn("trusted-verifier/src", workflow)
        self.assertIn("--skip-local-checks", workflow)
        self.assertIn("core.hooksPath=/dev/null", workflow)
        uses = re.findall(r"uses:\s*([^\s#]+)", workflow)
        self.assertTrue(uses)
        self.assertTrue(
            all(re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", value) for value in uses),
            uses,
        )
        self.assertIn("--require-hashes", workflow)
        self.assertIn("requirements-governance.lock", workflow)
        lock = (ROOT / "requirements-governance.lock").read_text(encoding="utf-8")
        self.assertIn("--hash=sha256:", lock)
        self.assertNotIn("python -m pip install -e .", workflow)

    def test_native_broker_rehearsal_runs_real_linux_and_macos_sockets(self):
        workflow = (ROOT / ".github/workflows/broker-native.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("os: [ubuntu-latest, macos-15]", workflow)
        self.assertIn("timeout-minutes: 10", workflow)
        source_green = workflow.index("Run source Green before packaging")
        build = workflow.index("python -m build --no-isolation --outdir")
        self.assertLess(source_green, build)
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("python -m sddgov.cli validate .", workflow)
        self.assertIn("python -m build --no-isolation --outdir", workflow)
        self.assertIn("SDDGOV_EXPECT_INSTALLED_WHEEL", workflow)
        self.assertIn('"${GITHUB_WORKSPACE}/tests/test_broker_native.py" -v', workflow)
        self.assertIn("pilot quick --output", workflow)
        self.assertIn("scripts/fresh_wheel_smoke.py", workflow)
        self.assertNotIn("PYTHONPATH: src", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)

        smoke = (ROOT / "scripts/fresh_wheel_smoke.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _installed_broker_smoke(", smoke)
        self.assertIn('"native_broker": broker_smoke', smoke)


if __name__ == "__main__":
    unittest.main()
