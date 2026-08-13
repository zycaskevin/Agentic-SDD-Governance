from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from .redaction import redact_files, write_report
from .schema_validation import bundled_schema, validate_instance


COLLECTORS = {
    "browser-console", "browser-har", "playwright-trace", "flutter-log",
    "android-logcat", "supabase-log", "docker-log", "terminal", "git",
}
PHASES = ("red", "evidence", "fix", "green", "proof")
REQUIRED_DOCS = {
    "red": ("reproduction.md",),
    "evidence": ("reproduction.md", "redaction-report.json"),
    "fix": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "redaction-report.json"),
    "green": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "regression-evidence.md", "verification.md", "redaction-report.json"),
    "proof": ("reproduction.md", "root-cause-hypothesis.md", "fix-scope.md", "regression-evidence.md", "verification.md", "rollback.md", "redaction-report.json"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resource_dir():
    return resources.files("sddgov").joinpath("resources/dep")


def _bounded_zone(dep: Path, relative: Path) -> Path:
    dep_root = dep.resolve()
    candidate = dep / relative
    candidate.mkdir(parents=True, exist_ok=True)
    resolved = candidate.resolve()
    try:
        actual_relative = resolved.relative_to(dep_root)
    except ValueError as exc:
        raise ValueError(f"evidence zone escapes DEP root: {relative}") from exc
    if actual_relative != relative:
        raise ValueError(f"evidence zone resolves unexpectedly: {relative}")
    return resolved


def _bounded_filename(directory: Path, name: str) -> Path:
    if not name or name in {".", ".."} or name.rstrip(" .") != name:
        raise ValueError("evidence filename is unsafe after platform normalization")
    candidate = (directory / name).resolve()
    if candidate.parent != directory.resolve():
        raise ValueError("evidence destination escapes its collector zone")
    return candidate


def make_dep(base: Path, issue: str, risk: str, sdd_ref: str | None = None, dep_id: str | None = None) -> Path:
    if risk not in {"L0", "L1", "L2", "L3"}:
        raise ValueError("risk must be L0, L1, L2, or L3")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_issue = "".join(c if c.isalnum() or c in "-_" else "-" for c in issue).strip("-") or "untracked"
    dep_id = dep_id or f"DEP-{stamp}-{safe_issue}"
    dep = base / dep_id
    if dep.exists():
        raise FileExistsError(f"DEP already exists: {dep}")
    (dep / "private" / "raw").mkdir(parents=True)
    (dep / "shareable" / "artifacts").mkdir(parents=True)
    for item in _resource_dir().iterdir():
        if item.name == "summary.yaml":
            continue
        (dep / item.name).write_bytes(item.read_bytes())
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
    _save(dep / "summary.yaml", summary)
    _save(dep / "manifest.json", {"schema_version": "1.0", "dep_id": dep_id, "raw": [], "shareable": []})
    return dep


def collect(dep: Path, collector: str, input_path: Path, label: str | None = None) -> Path:
    if collector not in COLLECTORS:
        raise ValueError(f"unsupported collector: {collector}")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    raw_dir = _bounded_zone(dep, Path("private/raw"))
    ordinal = len(_load(dep / "manifest.json").get("raw", [])) + 1
    default_label = f"artifact-{ordinal}{input_path.suffix.lower()}"
    safe_label = "".join(c if c.isalnum() or c in "-_." else "-" for c in (label or default_label))
    destination = _bounded_filename(raw_dir, f"{collector}--{safe_label}")
    shutil.copy2(input_path, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest_path = dep / "manifest.json"
    manifest = _load(manifest_path)
    manifest["raw"].append({
        "collector": collector,
        "path": str(destination.relative_to(dep.resolve())),
        "sha256": digest,
        "collected_at": utc_now(),
        "shareable": False,
    })
    _save(manifest_path, manifest)
    return destination


def redact(dep: Path) -> dict:
    raw_dir = _bounded_zone(dep, Path("private/raw"))
    shareable = _bounded_zone(dep, Path("shareable/artifacts"))
    files = sorted(p for p in raw_dir.iterdir() if p.is_file()) if raw_dir.exists() else []
    report = redact_files(files, shareable)
    report["dep_id"] = _load(dep / "summary.yaml")["dep_id"]
    report["generated_at"] = utc_now()
    write_report(report, dep / "redaction-report.json")
    manifest = _load(dep / "manifest.json")
    manifest["shareable"] = [
        {"path": f"shareable/artifacts/{row['output']}", "sha256": row["output_sha256"], "shareable": True}
        for row in report["files"]
    ]
    _save(dep / "manifest.json", manifest)
    return report


def transition(dep: Path, phase: str) -> dict:
    if phase not in PHASES:
        raise ValueError(f"phase must be one of: {', '.join(PHASES)}")
    summary_path = dep / "summary.yaml"
    summary = _load(summary_path)
    current = summary["workflow"]["phase"]
    if PHASES.index(phase) != PHASES.index(current) + 1:
        raise ValueError(f"transition must advance exactly one phase: {current} -> {phase}")
    previous = json.loads(json.dumps(summary))
    summary["workflow"]["phase"] = phase
    summary["workflow"]["history"].append({"phase": phase, "at": utc_now()})
    summary["updated_at"] = utc_now()
    _save(summary_path, summary)
    errors = verify(dep, strict=False)
    if errors:
        _save(summary_path, previous)
        raise ValueError(f"cannot enter {phase}: " + "; ".join(errors))
    return summary


def _has_real_content(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    meaningful = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return any("TODO" not in line and "<!--" not in line and "-->" not in line for line in meaningful)


def verify(dep: Path, strict: bool = False) -> list[str]:
    errors: list[str] = []
    for name in ("summary.yaml", "manifest.json"):
        if not (dep / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        return errors
    try:
        summary = _load(dep / "summary.yaml")
        manifest = _load(dep / "manifest.json")
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid machine-readable document: {exc}"]
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
    phase = summary.get("workflow", {}).get("phase")
    if phase not in PHASES:
        errors.append("invalid workflow phase")
        return errors
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
        path = dep / name
        if not path.is_file():
            errors.append(f"missing {name}")
        elif name.endswith(".md") and not _has_real_content(path):
            errors.append(f"template not completed: {name}")
    if PHASES.index(phase) >= PHASES.index("evidence") or strict:
        if not manifest.get("raw"):
            errors.append("no collected evidence")
        report_path = dep / "redaction-report.json"
        if report_path.is_file():
            report = _load(report_path)
            if report.get("blocked"):
                errors.append("redaction report contains blocked artifacts requiring manual review")
            if not manifest.get("shareable"):
                errors.append("no shareable redacted evidence")
    raw_refs = [
        attachment
        for attachment in summary.get("attachments", [])
        if isinstance(attachment, dict)
        and str(attachment.get("path", "")).startswith("private/")
    ]
    if raw_refs:
        errors.append("summary attachments must never reference private/raw evidence")
    return errors


def attach(dep: Path, target: str, output: Path | None = None) -> Path:
    if target not in {"issue", "commit", "pr", "changelog"}:
        raise ValueError("target must be issue, commit, pr, or changelog")
    errors = verify(dep, strict=True)
    if errors:
        raise ValueError("DEP is not attachable: " + "; ".join(errors))
    summary = _load(dep / "summary.yaml")
    manifest = _load(dep / "manifest.json")
    lines = [
        f"Evidence: {summary['dep_id']}",
        f"Issue: {summary['issue']}",
        f"SDD: {', '.join(summary.get('sdd_references') or ['n/a'])}",
        f"Risk: {summary['risk_level']}",
        "Workflow: Red -> Evidence -> Fix -> Green -> Proof",
        "Verified artifacts:",
    ]
    lines.extend(f"- `{row['path']}` (sha256: `{row['sha256']}`)" for row in manifest.get("shareable", []))
    lines.extend(["", f"Target: {target}"])
    output = output or dep / f"attach-{target}.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
