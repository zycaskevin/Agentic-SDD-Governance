from __future__ import annotations

import hashlib
import json
import re
import stat
import tempfile
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path, PurePosixPath

from .redaction import TEXT_SUFFIXES, redact_files, redact_text
from .schema_validation import bundled_schema, validate_instance


COLLECTORS = {
    "browser-console", "browser-har", "playwright-trace", "flutter-log",
    "android-logcat", "supabase-log", "docker-log", "terminal", "git",
}
PHASES = ("red", "evidence", "fix", "green", "proof")
DEP_ID_PATTERN = re.compile(r"^DEP-[A-Za-z0-9._-]+$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
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
    _require_regular_file(path, f"machine-readable document {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"machine-readable destination must not be a symlink: {path.name}")
    if path.exists() and not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"machine-readable destination must be a regular file: {path.name}")
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    temporary.replace(path)


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
    candidate_path = directory / name
    if candidate_path.is_symlink():
        raise ValueError("evidence destination must not be a symlink")
    candidate = candidate_path.resolve()
    if candidate.parent != directory.resolve():
        raise ValueError("evidence destination escapes its collector zone")
    return candidate


def _require_regular_file(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise FileNotFoundError(path) from exc
    if not stat.S_ISREG(mode):
        raise ValueError(f"{label} must be a regular file")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_artifact_path(dep: Path, value: object, zone: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"artifact path is invalid for {zone}")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or str(pure) != value
        or any(part in {"", ".", ".."} for part in pure.parts)
        or tuple(pure.parts[: len(PurePosixPath(zone).parts)])
        != PurePosixPath(zone).parts
        or pure.parent != PurePosixPath(zone)
    ):
        raise ValueError(f"artifact path escapes or is not normalized for {zone}: {value}")
    candidate = dep.joinpath(*pure.parts)
    current = dep
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"artifact path contains a symlink: {value}")
    try:
        candidate.absolute().relative_to(dep.absolute())
    except ValueError as exc:
        raise ValueError(f"artifact path escapes DEP root: {value}") from exc
    return candidate


def _actual_zone_files(dep: Path, zone: str) -> tuple[set[str], list[str]]:
    root = dep / zone
    if not root.exists():
        return set(), []
    if root.is_symlink():
        return set(), [f"artifact zone must not be a symlink: {zone}"]
    actual: set[str] = set()
    errors: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(dep).as_posix()
        if path.is_symlink():
            errors.append(f"artifact path contains a symlink: {relative}")
        elif path.is_dir():
            continue
        elif not stat.S_ISREG(path.lstat().st_mode):
            errors.append(f"artifact path is not a regular file: {relative}")
        else:
            actual.add(relative)
    return actual, errors


def make_dep(base: Path, issue: str, risk: str, sdd_ref: str | None = None, dep_id: str | None = None) -> Path:
    if risk not in {"L0", "L1", "L2", "L3"}:
        raise ValueError("risk must be L0, L1, L2, or L3")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_issue = "".join(c if c.isalnum() or c in "-_" else "-" for c in issue).strip("-") or "untracked"
    dep_id = dep_id or f"DEP-{stamp}-{safe_issue}"
    if not DEP_ID_PATTERN.fullmatch(dep_id):
        raise ValueError("DEP ID must match DEP-[A-Za-z0-9._-]+ and cannot contain a path")
    if base.is_symlink():
        raise ValueError("Evidence root must not be a symlink")
    base.mkdir(parents=True, exist_ok=True)
    base = base.resolve()
    dep = _bounded_filename(base, dep_id)
    if dep.exists():
        raise FileExistsError(f"DEP already exists: {dep}")
    (dep / "private" / "raw").mkdir(parents=True, mode=0o700)
    (dep / "private" / "raw").chmod(0o700)
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
    _require_regular_file(input_path, "collector input")
    raw_dir = _bounded_zone(dep, Path("private/raw"))
    raw_dir.chmod(0o700)
    manifest_path = dep / "manifest.json"
    _require_regular_file(manifest_path, "Evidence manifest")
    manifest = _load(manifest_path)
    ordinal = len(manifest.get("raw", [])) + 1
    default_label = f"artifact-{ordinal}{input_path.suffix.lower()}"
    safe_label = "".join(c if c.isalnum() or c in "-_." else "-" for c in (label or default_label))
    destination = _bounded_filename(raw_dir, f"{collector}--{safe_label}")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Evidence artifact already exists: {destination.name}")
    raw = input_path.read_bytes()
    with destination.open("xb") as handle:
        handle.write(raw)
    digest = hashlib.sha256(raw).hexdigest()
    manifest["raw"].append({
        "collector": collector,
        "path": str(destination.relative_to(dep.resolve())),
        "sha256": digest,
        "size": len(raw),
        "collected_at": utc_now(),
        "shareable": False,
    })
    _save(manifest_path, manifest)
    return destination


def redact(dep: Path) -> dict:
    raw_dir = _bounded_zone(dep, Path("private/raw"))
    shareable = _bounded_zone(dep, Path("shareable/artifacts"))
    files: list[Path] = []
    for path in sorted(raw_dir.iterdir()) if raw_dir.exists() else []:
        _require_regular_file(path, f"redaction source {path.name}")
        files.append(path)
    report = redact_files(files, shareable)
    report["dep_id"] = _load(dep / "summary.yaml")["dep_id"]
    report["generated_at"] = utc_now()
    _save(dep / "redaction-report.json", report)
    manifest = _load(dep / "manifest.json")
    raw_rows = manifest.get("raw", [])
    if not isinstance(raw_rows, list):
        raise ValueError("Evidence manifest raw must be an array")
    raw_by_name = {
        Path(row.get("path", "")).name: row
        for row in raw_rows
        if isinstance(row, dict)
    }
    if len(raw_by_name) != len(raw_rows):
        raise ValueError("Evidence manifest contains duplicate or invalid raw paths")
    for path in files:
        row = raw_by_name.get(path.name)
        if row is None:
            raise ValueError(f"raw artifact is not registered in manifest: {path.name}")
        row["sha256"] = _sha256_file(path)
        row["size"] = path.stat().st_size
    manifest["shareable"] = [
        {
            "path": f"shareable/artifacts/{row['output']}",
            "sha256": row["output_sha256"],
            "size": row["output_size"],
            "shareable": True,
        }
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


def _verify_manifest_artifacts(
    dep: Path, manifest: dict, *, portable: bool
) -> list[str]:
    errors: list[str] = []
    expected_paths: dict[str, set[str]] = {
        "private/raw": set(),
        "shareable/artifacts": set(),
    }
    row_contracts = {
        "raw": {
            "collector", "path", "sha256", "size", "collected_at", "shareable"
        },
        "shareable": {"path", "sha256", "size", "shareable"},
    }
    for kind, zone in (("raw", "private/raw"), ("shareable", "shareable/artifacts")):
        rows = manifest.get(kind)
        if not isinstance(rows, list):
            errors.append(f"manifest {kind} must be an array")
            continue
        for index, row in enumerate(rows):
            label = f"manifest {kind}[{index}]"
            if not isinstance(row, dict) or set(row) != row_contracts[kind]:
                errors.append(f"{label} has an invalid contract")
                continue
            if kind == "raw" and row.get("collector") not in COLLECTORS:
                errors.append(f"{label} has an unsupported collector")
            if kind == "raw" and (
                not isinstance(row.get("collected_at"), str)
                or not row["collected_at"].strip()
            ):
                errors.append(f"{label} collected_at is invalid")
            expected_shareable = kind == "shareable"
            if row.get("shareable") is not expected_shareable:
                errors.append(f"{label} shareable flag is invalid")
            if (
                not isinstance(row.get("size"), int)
                or isinstance(row.get("size"), bool)
                or row["size"] < 0
            ):
                errors.append(f"{label} size is invalid")
            if not isinstance(row.get("sha256"), str) or not SHA256_PATTERN.fullmatch(
                row["sha256"]
            ):
                errors.append(f"{label} sha256 is invalid")
            try:
                path = _manifest_artifact_path(dep, row.get("path"), zone)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            relative = path.relative_to(dep).as_posix()
            if relative in expected_paths[zone]:
                errors.append(f"duplicate manifest artifact path: {relative}")
                continue
            expected_paths[zone].add(relative)
            if not path.exists():
                if not (portable and kind == "raw"):
                    errors.append(f"missing artifact: {relative}")
                continue
            try:
                _require_regular_file(path, f"artifact {relative}")
            except (ValueError, FileNotFoundError) as exc:
                errors.append(str(exc))
                continue
            if isinstance(row.get("size"), int) and path.stat().st_size != row["size"]:
                errors.append(f"artifact size mismatch: {relative}")
            if isinstance(row.get("sha256"), str) and _sha256_file(path) != row["sha256"]:
                errors.append(f"artifact sha256 mismatch: {relative}")

    for zone, expected in expected_paths.items():
        actual, zone_errors = _actual_zone_files(dep, zone)
        errors.extend(zone_errors)
        extras = sorted(actual - expected)
        if extras:
            errors.append(
                f"unregistered artifacts in {zone}: " + ", ".join(extras)
            )
    return errors


def _verify_redaction_associations(dep: Path, manifest: dict, report: dict) -> list[str]:
    errors: list[str] = []
    required_report = {
        "schema_version", "files", "blocked", "totals", "dep_id", "generated_at"
    }
    if set(report) != required_report or report.get("schema_version") != "1.0":
        return ["redaction report has an invalid contract"]
    if report.get("dep_id") != manifest.get("dep_id"):
        errors.append("redaction report dep_id does not match manifest")
    files = report.get("files")
    if not isinstance(files, list):
        return errors + ["redaction report files must be an array"]
    raw_rows = {
        Path(row["path"]).name: row
        for row in manifest.get("raw", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    shareable_rows = {
        Path(row["path"]).name: row
        for row in manifest.get("shareable", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    expected_fields = {
        "source", "output", "source_sha256", "source_size",
        "output_sha256", "output_size", "redactions",
    }
    seen_sources: set[str] = set()
    seen_outputs: set[str] = set()
    computed_totals: dict[str, int] = {}
    for index, row in enumerate(files):
        label = f"redaction report files[{index}]"
        if not isinstance(row, dict) or set(row) != expected_fields:
            errors.append(f"{label} has an invalid contract")
            continue
        source = row.get("source")
        output = row.get("output")
        if (
            not isinstance(source, str)
            or not source
            or Path(source).name != source
            or not isinstance(output, str)
            or not output
            or Path(output).name != output
        ):
            errors.append(f"{label} contains an invalid source or output name")
            continue
        if source in seen_sources or output in seen_outputs:
            errors.append(f"{label} duplicates a source or output association")
            continue
        seen_sources.add(source)
        seen_outputs.add(output)
        raw = raw_rows.get(source)
        shareable = shareable_rows.get(output)
        if raw is None or shareable is None:
            errors.append(f"{label} is not fully associated with manifest artifacts")
            continue
        for report_key, manifest_key, manifest_row in (
            ("source_sha256", "sha256", raw),
            ("source_size", "size", raw),
            ("output_sha256", "sha256", shareable),
            ("output_size", "size", shareable),
        ):
            if row.get(report_key) != manifest_row.get(manifest_key):
                errors.append(f"{label} {report_key} does not match manifest")
        redactions = row.get("redactions")
        if not isinstance(redactions, dict) or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
            for key, value in redactions.items()
        ):
            errors.append(f"{label} redactions are invalid")
        else:
            for key, value in redactions.items():
                computed_totals[key] = computed_totals.get(key, 0) + value

        try:
            raw_path = _manifest_artifact_path(dep, raw["path"], "private/raw")
            output_path = _manifest_artifact_path(
                dep, shareable["path"], "shareable/artifacts"
            )
        except (KeyError, ValueError):
            continue
        if output_path.exists() and output_path.suffix.lower() in TEXT_SUFFIXES:
            try:
                output_text = output_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"{label} shareable text is not valid UTF-8")
            else:
                rescanned_output, _ = redact_text(output_text)
                if rescanned_output != output_text:
                    errors.append(f"{label} shareable output still matches redaction rules")
                if raw_path.exists():
                    try:
                        raw_text = raw_path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        errors.append(f"{label} raw text is not valid UTF-8")
                    else:
                        expected_output, expected_redactions = redact_text(raw_text)
                        if output_text != expected_output:
                            errors.append(
                                f"{label} output is not the deterministic redaction of source"
                            )
                        if redactions != expected_redactions:
                            errors.append(
                                f"{label} redaction counts do not match recalculation"
                            )
    if seen_outputs != set(shareable_rows):
        errors.append("redaction report does not cover every shareable artifact")
    if report.get("totals") != computed_totals:
        errors.append("redaction report totals do not match file associations")
    return errors


def verify(dep: Path, strict: bool = False, portable: bool = False) -> list[str]:
    errors: list[str] = []
    if portable and not strict:
        errors.append("portable verification requires strict mode")
    if dep.is_symlink():
        errors.append("DEP root must not be a symlink")
    for name in ("summary.yaml", "manifest.json"):
        try:
            _require_regular_file(dep / name, name)
        except FileNotFoundError:
            errors.append(f"missing {name}")
        except ValueError as exc:
            errors.append(str(exc))
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
    if (
        set(manifest) != {"schema_version", "dep_id", "raw", "shareable"}
        or manifest.get("schema_version") != "1.0"
    ):
        errors.append("manifest has an invalid root contract")
    if manifest.get("dep_id") != summary.get("dep_id"):
        errors.append("manifest dep_id does not match summary")
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
        try:
            _require_regular_file(path, name)
        except FileNotFoundError:
            errors.append(f"missing {name}")
            continue
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if name.endswith(".md") and not _has_real_content(path):
            errors.append(f"template not completed: {name}")
    if PHASES.index(phase) >= PHASES.index("evidence") or strict:
        if not manifest.get("raw"):
            errors.append("no collected evidence")
        report_path = dep / "redaction-report.json"
        if report_path.is_file():
            try:
                report = _load(report_path)
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"invalid redaction report: {exc}")
            else:
                if report.get("blocked"):
                    errors.append("redaction report contains blocked artifacts requiring manual review")
                if not manifest.get("shareable"):
                    errors.append("no shareable redacted evidence")
                errors.extend(_verify_redaction_associations(dep, manifest, report))
        errors.extend(_verify_manifest_artifacts(dep, manifest, portable=portable))
    raw_refs = [
        attachment
        for attachment in summary.get("attachments", [])
        if isinstance(attachment, dict)
        and str(attachment.get("path", "")).startswith("private/")
    ]
    if raw_refs:
        errors.append("summary attachments must never reference private/raw evidence")
    shareable_by_path = {
        row.get("path"): row
        for row in manifest.get("shareable", [])
        if isinstance(row, dict)
    }
    for attachment in summary.get("attachments", []):
        if not isinstance(attachment, dict):
            continue
        registered = shareable_by_path.get(attachment.get("path"))
        if registered is None or registered.get("sha256") != attachment.get("sha256"):
            errors.append("summary attachment is not bound to a matching shareable artifact")
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
    if output.is_symlink():
        raise ValueError("attachment output must not be a symlink")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
