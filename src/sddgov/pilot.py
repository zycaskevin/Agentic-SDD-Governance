from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .autonomy import evaluate_escalation
from .evidence import collect, make_dep, redact, transition, verify
from .installer import doctor, setup_agent


def _complete(dep: Path, name: str, text: str) -> None:
    (dep / name).write_text(f"# Synthetic Muse Pilot\n\n{text}\n", encoding="utf-8")


def _proof_dep(dep: Path) -> None:
    transition(dep, "evidence")
    _complete(
        dep,
        "root-cause-hypothesis.md",
        "The synthetic client treated an API conflict as persistence success; the API status falsifies the optimistic UI hypothesis.",
    )
    _complete(
        dep,
        "fix-scope.md",
        "Handle the conflict and preserve confirmed-only relationship facts; no product behavior or real data is changed.",
    )
    transition(dep, "fix")
    _complete(
        dep,
        "regression-evidence.md",
        "A synthetic contract test now rejects the conflict and preserves the confirmed-only boundary.",
    )
    _complete(
        dep,
        "verification.md",
        "The original synthetic reproduction and the bounded regression set pass.",
    )
    transition(dep, "green")
    _complete(
        dep,
        "rollback.md",
        "Rollback version 1.0: revert the bounded synthetic patch and rerun the contract test.",
    )
    transition(dep, "proof")


def run_synthetic_muse_pilot(output: Path | None = None) -> dict[str, Any]:
    """Run a disposable, offline Muse-shaped pilot with synthetic data only."""
    with tempfile.TemporaryDirectory(prefix="sdg-synthetic-muse-") as temporary:
        clone = Path(temporary) / "Muse-synthetic-clone"
        clone.mkdir()
        (clone / "README.md").write_text(
            "# Synthetic Muse Clone\n\nNo real user, relationship, image, or credential data.\n",
            encoding="utf-8",
        )
        installed = setup_agent(clone, "hermes", "team-standard")
        health = doctor(clone)

        # A real binary image must never be auto-declared shareable.
        blocked_dep = make_dep(
            clone / "evidence",
            issue="SYNTH-MUSE-IMAGE",
            risk="L1",
            dep_id="DEP-SYNTH-MUSE-IMAGE-001",
        )
        _complete(blocked_dep, "reproduction.md", "One generated 1x1 image enters the local Evidence boundary.")
        image = clone / "synthetic-single-image.png"
        image.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        )
        collect(blocked_dep, "browser-console", image, label="single-image.png")
        blocked_report = redact(blocked_dep)
        blocked_errors = verify(blocked_dep, strict=True)

        # The successful pilot uses synthetic text plus a reviewed metadata derivative.
        dep = make_dep(
            clone / "evidence",
            issue="SYNTH-MUSE-CONFIRMED-FACT",
            risk="L1",
            sdd_ref="SYNTH-MUSE-SDD-001",
            dep_id="DEP-SYNTH-MUSE-PILOT-001",
        )
        _complete(
            dep,
            "reproduction.md",
            "Submit a synthetic relationship note, observe success, reload, and detect that no confirmed fact was persisted.",
        )
        runtime = clone / "synthetic-runtime.log"
        runtime.write_text(
            "Authorization: Bearer synthetic-not-a-real-token\n"
            "owner=synthetic.person@example.invalid\n"
            "POST /relationship-facts -> 409 confirmation_required\n",
            encoding="utf-8",
        )
        image_metadata = clone / "single-image-reviewed-metadata.json"
        image_metadata.write_text(
            json.dumps(
                {
                    "fixture": "synthetic-single-image",
                    "pixels": "1x1",
                    "contains_real_person": False,
                    "visual_derivative_reviewed": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        collect(dep, "browser-console", runtime, label="runtime.log")
        collect(dep, "browser-console", image_metadata, label="single-image.json")
        redaction_report = redact(dep)
        _proof_dep(dep)
        strict_errors = verify(dep, strict=True)
        shareable_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((dep / "shareable/artifacts").iterdir())
        )
        for raw_path in (dep / "private/raw").iterdir():
            raw_path.unlink()
        portable_errors = verify(dep, strict=True, portable=True)

        result = {
            "schema_version": "1.0",
            "pilot": "synthetic-muse-isolated",
            "network_used": False,
            "real_data_used": False,
            "agent_install_ok": installed.get("ok") is True and health.get("ok") is True,
            "binary_image_fail_closed": bool(blocked_report["blocked"])
            and any("blocked artifacts" in error for error in blocked_errors),
            "text_redaction_ok": "synthetic-not-a-real-token" not in shareable_text
            and "synthetic.person@example.invalid" not in shareable_text,
            "strict_dep_ok": not strict_errors,
            "portable_dep_ok": not portable_errors,
            "symlink_path_escape_duplicate_tests": "covered_by_adversarial_test_suite",
            "verdict": "PASS"
            if all(
                (
                    installed.get("ok") is True,
                    health.get("ok") is True,
                    bool(blocked_report["blocked"]),
                    any("blocked artifacts" in error for error in blocked_errors),
                    "synthetic-not-a-real-token" not in shareable_text,
                    "synthetic.person@example.invalid" not in shareable_text,
                    not strict_errors,
                    not portable_errors,
                    not redaction_report["blocked"],
                )
            )
            else "FAIL",
        }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result


def run_quick_demo(output: Path | None = None) -> dict[str, Any]:
    """Demonstrate the core allow/block/evidence boundaries with synthetic data."""
    with tempfile.TemporaryDirectory(prefix="sdg-quick-demo-") as temporary:
        evaluation_root = Path(temporary)
        routine = evaluate_escalation(
            evaluation_root,
            {
                "risk_level": "L1",
                "category": "implementation",
                "effects": {},
            },
        )
        disguised_dangerous = evaluate_escalation(
            evaluation_root,
            {
                "risk_level": "L1",
                "category": "implementation",
                "effects": {"destructive": True, "production": True},
            },
        )
    evidence_pilot = run_synthetic_muse_pilot()
    required_checks = {
        "routine_l1_continues": routine.get("state") == "CONTINUE",
        "dangerous_downgrade_blocked": (
            disguised_dangerous.get("state") == "BLOCKED"
            and disguised_dangerous.get("reason")
            == "dangerous_action_cannot_be_downgraded"
        ),
        "agent_install_ok": evidence_pilot.get("agent_install_ok") is True,
        "text_redaction_ok": evidence_pilot.get("text_redaction_ok") is True,
        "binary_evidence_fail_closed": (
            evidence_pilot.get("binary_image_fail_closed") is True
        ),
        "strict_dep_ok": evidence_pilot.get("strict_dep_ok") is True,
    }
    result = {
        "schema_version": "1.0",
        "demo": "sdg-quick-offline",
        "network_used": False,
        "real_data_used": False,
        **required_checks,
        "verdict": (
            "PASS"
            if all(required_checks.values())
            and evidence_pilot.get("verdict") == "PASS"
            else "FAIL"
        ),
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result
