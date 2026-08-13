from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from . import __version__
from .governance import PROFILES, emit_event, init_project


AGENTS = ("codex", "hermes")
MANAGED_ROOT = ".agentic-sdd-governance"
SKILL_ROOT = ".agents/skills/agentic-sdd-governance"
MANIFEST_PATH = f"{MANAGED_ROOT}/manifest.json"
START_MARKER = "<!-- agentic-sdd-governance:start -->"
END_MARKER = "<!-- agentic-sdd-governance:end -->"
GITIGNORE_START_MARKER = "# agentic-sdd-governance:start"
GITIGNORE_END_MARKER = "# agentic-sdd-governance:end"
GITIGNORE_BLOCK = (
    f"{GITIGNORE_START_MARKER}\n"
    "# Raw Debug Evidence Packages stay local.\n"
    "evidence/**/private/raw/\n"
    "# Runtime locks are local coordination state.\n"
    ".sddgov/*.lock\n"
    "# Merge Gate, independent review receipts, and trusted approver public keys are auditable project policy.\n"
    "# Owner private signing keys must never enter the repository.\n"
    f"{GITIGNORE_END_MARKER}"
)


def _stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"project directory does not exist: {resolved}")
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve():
        raise ValueError("refusing to manage a filesystem root or home directory")
    return resolved


def _walk_resource(node, prefix: PurePosixPath = PurePosixPath()) -> Iterable[tuple[str, bytes]]:
    for child in sorted(node.iterdir(), key=lambda item: item.name):
        relative = prefix / child.name
        if child.is_dir():
            yield from _walk_resource(child, relative)
        elif child.is_file():
            yield relative.as_posix(), child.read_bytes()


def _resource_files() -> dict[str, bytes]:
    root = resources.files("sddgov").joinpath("resources", "governance")
    return dict(_walk_resource(root))


def _desired_files() -> tuple[dict[str, bytes], dict[str, bytes]]:
    source = _resource_files()
    desired: dict[str, bytes] = {}
    for relative, content in source.items():
        skill_prefix = "skill/agentic-sdd-governance/"
        if relative.startswith(skill_prefix):
            destination = f"{SKILL_ROOT}/{relative.removeprefix(skill_prefix)}"
        elif relative.startswith("adapters/"):
            continue
        else:
            destination = f"{MANAGED_ROOT}/{relative}"
        desired[destination] = content
    return source, desired


def _managed_path(root: Path, relative: str) -> Path:
    if not (
        relative.startswith(f"{MANAGED_ROOT}/")
        or relative.startswith(f"{SKILL_ROOT}/")
    ):
        raise ValueError(f"manifest contains unmanaged path: {relative}")
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"manifest path escapes project: {relative}") from exc
    return target


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest(root: Path) -> dict[str, Any] | None:
    path = root / MANIFEST_PATH
    return _read_json(path) if path.is_file() else None


def _adapter_block(source: dict[str, bytes], agent: str) -> str:
    key = f"adapters/{agent}/AGENTS.md"
    if key not in source:
        raise FileNotFoundError(f"packaged adapter is missing: {key}")
    body = source[key].decode("utf-8").strip()
    return f"{START_MARKER}\n{body}\n{END_MARKER}"


def _extract_marked_block(text: str, start_marker: str, end_marker: str, label: str) -> str | None:
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 and end < 0:
        return None
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"{label} contains a malformed Agentic SDD Governance block")
    if text.find(start_marker, start + 1) >= 0 or text.find(end_marker, end + 1) >= 0:
        raise ValueError(f"{label} contains duplicate Agentic SDD Governance blocks")
    return text[start : end + len(end_marker)]


def _extract_block(text: str) -> str | None:
    return _extract_marked_block(text, START_MARKER, END_MARKER, "AGENTS.md")


def _extract_gitignore_block(text: str) -> str | None:
    return _extract_marked_block(
        text, GITIGNORE_START_MARKER, GITIGNORE_END_MARKER, ".gitignore"
    )


def _upsert_block(path: Path, block: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    current = _extract_block(existing)
    if current is None:
        updated = f"{existing.rstrip()}\n\n{block}\n" if existing.strip() else f"{block}\n"
    else:
        updated = existing.replace(current, block)
        if not updated.endswith("\n"):
            updated += "\n"
    path.write_text(updated, encoding="utf-8")


def _upsert_gitignore(path: Path) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    current = _extract_gitignore_block(existing)
    if current is None:
        updated = (
            f"{existing.rstrip()}\n\n{GITIGNORE_BLOCK}\n"
            if existing.strip()
            else f"{GITIGNORE_BLOCK}\n"
        )
    else:
        updated = existing.replace(current, GITIGNORE_BLOCK)
        if not updated.endswith("\n"):
            updated += "\n"
    path.write_text(updated, encoding="utf-8")


def _remove_block(path: Path) -> bool:
    if not path.exists():
        return False
    existing = path.read_text(encoding="utf-8")
    block = _extract_block(existing)
    if block is None:
        return False
    before, after = existing.split(block, 1)
    if before.strip() and after.strip():
        updated = f"{before.rstrip()}\n\n{after.lstrip()}"
    else:
        updated = f"{before}{after}".strip()
        if updated:
            updated += "\n"
    if updated:
        path.write_text(updated, encoding="utf-8")
    else:
        path.unlink()
    return True


def _remove_gitignore_block(path: Path) -> bool:
    if not path.exists():
        return False
    existing = path.read_text(encoding="utf-8")
    block = _extract_gitignore_block(existing)
    if block is None:
        return False
    before, after = existing.split(block, 1)
    if before.strip() and after.strip():
        updated = f"{before.rstrip()}\n\n{after.lstrip()}"
    else:
        updated = f"{before}{after}".strip()
        if updated:
            updated += "\n"
    if updated:
        path.write_text(updated, encoding="utf-8")
    else:
        path.unlink()
    return True


def _current_hash(path: Path) -> str | None:
    return _sha256(path.read_bytes()) if path.is_file() else None


def _installation_errors(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "1.0":
        errors.append("unsupported install manifest schema")
    if manifest.get("agent") not in AGENTS:
        errors.append("manifest agent is invalid")
    if manifest.get("profile") not in PROFILES:
        errors.append("manifest profile is invalid")
    managed = manifest.get("managed_files")
    if not isinstance(managed, dict):
        return errors + ["manifest managed_files must be an object"]
    if manifest.get("governance_version") == __version__:
        expected = set(_desired_files()[1])
        actual = set(managed)
        for relative in sorted(expected - actual):
            errors.append(f"manifest omitted managed file: {relative}")
        for relative in sorted(actual - expected):
            errors.append(f"manifest contains unexpected managed file: {relative}")
    for relative, expected in managed.items():
        try:
            path = _managed_path(root, relative)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        actual = _current_hash(path)
        if actual is None:
            errors.append(f"missing managed file: {relative}")
        elif actual != expected:
            errors.append(f"modified managed file: {relative}")
    agents_path = root / "AGENTS.md"
    try:
        block = _extract_block(agents_path.read_text(encoding="utf-8")) if agents_path.exists() else None
    except ValueError as exc:
        errors.append(str(exc))
        block = None
    if block is None:
        errors.append("AGENTS.md governance block is missing")
    elif _sha256(block.encode("utf-8")) != manifest.get("agents_block_sha256"):
        errors.append("AGENTS.md governance block was modified")
    gitignore_path = root / ".gitignore"
    try:
        gitignore_block = (
            _extract_gitignore_block(gitignore_path.read_text(encoding="utf-8"))
            if gitignore_path.exists()
            else None
        )
    except ValueError as exc:
        errors.append(str(exc))
        gitignore_block = None
    if gitignore_block is None:
        errors.append(".gitignore raw-evidence block is missing")
    elif _sha256(gitignore_block.encode("utf-8")) != manifest.get("gitignore_block_sha256"):
        errors.append(".gitignore raw-evidence block was modified")
    state = root / ".sddgov" / "project.json"
    if not state.is_file():
        errors.append(".sddgov/project.json is missing")
    else:
        try:
            project = _read_json(state)
            if project.get("profile") != manifest.get("profile"):
                errors.append(".sddgov profile does not match install manifest")
            if project.get("governance_version") != manifest.get("governance_version"):
                errors.append(".sddgov version does not match install manifest")
        except (json.JSONDecodeError, OSError):
            errors.append(".sddgov/project.json is invalid")
    return errors


def doctor(root: Path) -> dict[str, Any]:
    root = _safe_root(root)
    manifest = _load_manifest(root)
    if manifest is None:
        return {
            "ok": False,
            "project": str(root),
            "errors": [f"{MANIFEST_PATH} is missing; run sddgov setup-agent"],
            "warnings": [],
        }
    errors = _installation_errors(root, manifest)
    warnings: list[str] = []
    if manifest.get("governance_version") != __version__:
        warnings.append(
            f"installed governance version {manifest.get('governance_version')} differs from CLI {__version__}"
        )
    return {
        "ok": not errors,
        "project": str(root),
        "agent": manifest.get("agent"),
        "profile": manifest.get("profile"),
        "governance_version": manifest.get("governance_version"),
        "managed_file_count": len(manifest.get("managed_files", {})),
        "errors": errors,
        "warnings": warnings,
    }


def setup_agent(root: Path, agent: str, profile: str, force: bool = False) -> dict[str, Any]:
    root = _safe_root(root)
    if agent not in AGENTS:
        raise ValueError(f"agent must be one of: {', '.join(AGENTS)}")
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of: {', '.join(PROFILES)}")
    source, desired = _desired_files()
    block = _adapter_block(source, agent)
    agents_path = root / "AGENTS.md"
    if agents_path.exists():
        _extract_block(agents_path.read_text(encoding="utf-8"))
    gitignore_path = root / ".gitignore"
    if gitignore_path.exists():
        _extract_gitignore_block(gitignore_path.read_text(encoding="utf-8"))
    state_path = root / ".sddgov" / "project.json"
    state_before: dict[str, Any] | None = None
    if state_path.exists():
        try:
            state_before = _read_json(state_path)
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError("existing .sddgov/project.json is invalid") from exc
        if state_before.get("profile") != profile and not force:
            raise ValueError("existing .sddgov profile differs; inspect and rerun with --force")
    existing = _load_manifest(root)
    if existing is not None:
        errors = _installation_errors(root, existing)
        same_config = (
            existing.get("agent") == agent
            and existing.get("profile") == profile
            and existing.get("governance_version") == __version__
        )
        if not errors and same_config and not force:
            return {
                "ok": True,
                "status": "already-installed",
                "project": str(root),
                "agent": agent,
                "profile": profile,
                "governance_version": __version__,
                "managed_file_count": len(existing.get("managed_files", {})),
            }
        if not force:
            detail = "; ".join(errors) if errors else "agent, profile, or version differs"
            raise ValueError(f"existing installation differs: {detail}; inspect with doctor or rerun with --force")
    elif not force:
        conflicts = [relative for relative in desired if (root / relative).exists()]
        if agents_path.exists() and _extract_block(agents_path.read_text(encoding="utf-8")) is not None:
            conflicts.append("AGENTS.md governance block")
        if (
            gitignore_path.exists()
            and _extract_gitignore_block(gitignore_path.read_text(encoding="utf-8")) is not None
        ):
            conflicts.append(".gitignore raw-evidence block")
        if conflicts:
            raise FileExistsError(f"unmanaged install target exists: {conflicts[0]}; use --force after review")

    if existing is not None:
        for relative in existing.get("managed_files", {}):
            if relative not in desired:
                path = _managed_path(root, relative)
                if path.is_file():
                    path.unlink()

    for relative, content in desired.items():
        destination = _managed_path(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    _upsert_block(root / "AGENTS.md", block)
    _upsert_gitignore(gitignore_path)

    created_state = init_project(root, profile)
    state = _read_json(state_path)
    if state.get("profile") != profile or state.get("governance_version") != __version__:
        previous_profile = state.get("profile")
        previous_version = state.get("governance_version")
        state["profile"] = profile
        state["governance_version"] = __version__
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        event_type = (
            "governance_profile_updated"
            if previous_profile != profile
            else "governance_version_updated"
        )
        emit_event(
            root,
            event_type,
            "L0",
            {
                "previous_profile": previous_profile,
                "profile": profile,
                "previous_governance_version": previous_version,
                "governance_version": __version__,
            },
        )

    managed_hashes = {
        relative: _current_hash(_managed_path(root, relative)) for relative in sorted(desired)
    }
    manifest = {
        "schema_version": "1.0",
        "governance_version": __version__,
        "agent": agent,
        "profile": profile,
        "installed_at": _stamp(),
        "managed_files": managed_hashes,
        "agents_block_sha256": _sha256(block.encode("utf-8")),
        "gitignore_block_sha256": _sha256(GITIGNORE_BLOCK.encode("utf-8")),
        "uninstall_retains": [".sddgov", "evidence/*/shareable"],
        "uninstall_local_cleanup_required": {
            "path": "evidence/*/private/raw",
            "owner": "repository owner",
            "retention": "review and remove under the repository retention policy; uninstall does not delete unmanaged evidence",
        },
    }
    manifest_path = root / MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "status": "installed" if existing is None else "updated",
        "project": str(root),
        "agent": agent,
        "profile": profile,
        "governance_version": __version__,
        "managed_file_count": len(managed_hashes),
        "created_state": [str(path.relative_to(root)) for path in created_state],
    }


def _remove_empty_parents(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _remove_empty_tree(path: Path) -> None:
    if not path.is_dir():
        return
    directories = sorted(
        (item for item in path.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass
    try:
        path.rmdir()
    except OSError:
        pass


def uninstall_agent(root: Path, force: bool = False) -> dict[str, Any]:
    root = _safe_root(root)
    manifest = _load_manifest(root)
    if manifest is None:
        raise FileNotFoundError(f"{MANIFEST_PATH} is missing; nothing to uninstall")
    errors = _installation_errors(root, manifest)
    blocking = [
        error
        for error in errors
        if "managed file" in error or "AGENTS.md" in error or ".gitignore" in error
    ]
    if blocking and not force:
        raise ValueError(f"installation was modified: {'; '.join(blocking)}; rerun with --force after review")
    removed: list[str] = []
    for relative in sorted(manifest.get("managed_files", {}), reverse=True):
        path = _managed_path(root, relative)
        if path.is_file() or path.is_symlink():
            path.unlink()
            removed.append(relative)
    manifest_path = root / MANIFEST_PATH
    if manifest_path.exists():
        manifest_path.unlink()
        removed.append(MANIFEST_PATH)
    _remove_block(root / "AGENTS.md")
    _remove_gitignore_block(root / ".gitignore")
    _remove_empty_tree(root / MANAGED_ROOT)
    _remove_empty_tree(root / SKILL_ROOT)
    _remove_empty_parents((root / SKILL_ROOT).parent, root)
    return {
        "ok": True,
        "status": "uninstalled",
        "project": str(root),
        "removed_file_count": len(removed),
        "retained": list(manifest.get("uninstall_retains", [".sddgov"])),
        "local_cleanup_required": manifest.get(
            "uninstall_local_cleanup_required",
            {
                "path": "evidence/*/private/raw",
                "owner": "repository owner",
                "retention": "review and remove under the repository retention policy",
            },
        ),
    }
