from __future__ import annotations

import hashlib
import os
import re
import stat
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern[str]
    replacement: str


PROVIDER_CREDENTIAL_PATTERN = re.compile(
    r"\b(?:"
    r"(?:AKIA|ASIA|AIDA|AROA|AIPA|ANPA|ANVA|ASCA)[A-Z0-9]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{36,255}"
    r"|github_pat_[A-Za-z0-9_]{60,255}"
    r"|sk-(?:proj-)?[A-Za-z0-9_-]{20,}"
    r"|sk_live_[A-Za-z0-9]{20,}"
    r")\b"
)


RULES: tuple[Rule, ...] = (
    Rule("private-key", re.compile(r"-----BEGIN [^-]*(?:PRIVATE KEY|OPENSSH PRIVATE KEY)-----.*?-----END [^-]*(?:PRIVATE KEY|OPENSSH PRIVATE KEY)-----", re.I | re.S), "[REDACTED_PRIVATE_KEY]"),
    Rule("authorization", re.compile(r"(?im)^(authorization\s*:\s*)(?:bearer\s+)?[^\r\n]+"), r"\1[REDACTED_AUTHORIZATION]"),
    Rule("cookie", re.compile(r"(?im)^((?:set-)?cookie\s*:\s*)[^\r\n]+"), r"\1[REDACTED_COOKIE]"),
    Rule("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "[REDACTED_JWT]"),
    Rule("provider-credential", PROVIDER_CREDENTIAL_PATTERN, "[REDACTED_PROVIDER_CREDENTIAL]"),
    Rule("password", re.compile(r'''(?i)((?:"|')?(?:[A-Z0-9]+_)*(?:password|passwd)(?:"|')?\s*[=:]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)'''), r"\1[REDACTED_PASSWORD]"),
    Rule("secret-field", re.compile(r'''(?i)((?:"|')?(?:[A-Z0-9]+[_-])*(?:secret(?:[_-]?key)?|api[_-]?key|access[_-]?(?:token|key)|refresh[_-]?token|client[_-]?secret)(?:[_-][A-Z0-9]+)*(?:"|')?\s*[=:]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)'''), r"\1[REDACTED_SECRET]"),
    Rule("patient-identifier", re.compile(r'''(?i)((?:"|')?\bpatient[_-]?(?:id|identifier)\b(?:"|')?\s*[=:]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)'''), r"\1[REDACTED_PATIENT_IDENTIFIER]"),
    Rule("customer-identifier", re.compile(r'''(?i)((?:"|')?\bcustomer[_-]?(?:id|identifier)\b(?:"|')?\s*[=:]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)'''), r"\1[REDACTED_CUSTOMER_IDENTIFIER]"),
    Rule(
        "home-path",
        re.compile(r'''(?<!\w)/(?:home|Users)/[^\s'"<>]+'''),
        "[REDACTED_HOME_PATH]",
    ),
    Rule("email", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[REDACTED_EMAIL]"),
    Rule("phone", re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)"), "[REDACTED_PHONE_OR_NUMBER]"),
    Rule("card-like", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"), "[REDACTED_CARD_OR_NUMBER]"),
    Rule("trailing-whitespace", re.compile(r"[ \t]+(?=\r?$)", re.M), ""),
)


TEXT_SUFFIXES = {
    ".txt", ".log", ".json", ".jsonl", ".yaml", ".yml", ".xml", ".md",
    ".csv", ".tsv", ".html", ".js", ".ts", ".dart", ".sh",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    output = text
    for rule in RULES:
        output, count = rule.pattern.subn(rule.replacement, output)
        if count:
            counts[rule.rule_id] = count
    if PROVIDER_CREDENTIAL_PATTERN.search(output):
        raise ValueError("unredacted known provider credential identifier")
    return output, counts


def _open_directory(path: Path, label: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"{label} cannot be opened safely: {exc}") from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise ValueError(f"{label} must be a directory")
    return descriptor


def _write_at(
    directory_fd: int,
    name: str,
    data: bytes,
    published_outputs: dict[str, tuple[int, int]] | None = None,
) -> None:
    try:
        existing = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        existing = None
    if existing is not None and stat.S_ISLNK(existing.st_mode):
        raise ValueError(f"redaction destination must not be a symlink: {name}")
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise ValueError(f"redaction destination must be a regular file: {name}")
    temporary = f".{name}.{secrets.token_hex(16)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(temporary, flags, 0o600, dir_fd=directory_fd)
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(
            temporary,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        published = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if published_outputs is not None:
            published_outputs[name] = (published.st_dev, published.st_ino)
        os.fsync(directory_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def redact_files(
    files: Iterable[Path],
    output_dir: Path,
    *,
    metadata_by_name: dict[str, dict[str, str]] | None = None,
    source_dir_fd: int | None = None,
    output_dir_fd: int | None = None,
    published_outputs: dict[str, tuple[int, int]] | None = None,
) -> dict:
    if output_dir.is_symlink():
        raise ValueError("redaction output directory must not be a symlink")
    output_dir.mkdir(parents=True, exist_ok=True)
    owned_output_fd = output_dir_fd is None
    active_output_fd = (
        _open_directory(output_dir, "redaction output directory")
        if owned_output_fd
        else output_dir_fd
    )
    if active_output_fd is None:
        raise ValueError("redaction output directory is unavailable")
    report = {"schema_version": "1.0", "files": [], "blocked": [], "totals": {}}
    try:
        for source in files:
            rel_name = source.name
            owned_source_fd = source_dir_fd is None
            active_source_fd = (
                _open_directory(source.parent, f"redaction source directory for {rel_name}")
                if owned_source_fd
                else source_dir_fd
            )
            if active_source_fd is None:
                raise ValueError(f"redaction source directory is unavailable: {rel_name}")
            flags = (
                os.O_RDONLY
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                before = os.stat(rel_name, dir_fd=active_source_fd, follow_symlinks=False)
            except FileNotFoundError as exc:
                if owned_source_fd:
                    os.close(active_source_fd)
                raise ValueError(f"redaction source disappeared: {rel_name}") from exc
            if stat.S_ISLNK(before.st_mode):
                if owned_source_fd:
                    os.close(active_source_fd)
                raise ValueError(f"redaction source must not be a symlink: {rel_name}")
            try:
                descriptor = os.open(rel_name, flags, dir_fd=active_source_fd)
            except OSError as exc:
                if owned_source_fd:
                    os.close(active_source_fd)
                raise ValueError(f"redaction source cannot be opened safely: {rel_name}") from exc
            try:
                current = os.fstat(descriptor)
                if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
                    raise ValueError(
                        f"redaction source must be a non-linked regular file: {rel_name}"
                    )
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                raw = b"".join(chunks)
            finally:
                os.close(descriptor)
                if owned_source_fd:
                    os.close(active_source_fd)
            artifact_metadata = (metadata_by_name or {}).get(rel_name, {})
            is_har = (
                artifact_metadata.get("collector") == "browser-har"
                or artifact_metadata.get("media_type") == "application/har+json"
                or source.suffix.lower() == ".har"
            )
            if is_har or source.suffix.lower() not in TEXT_SUFFIXES:
                report["blocked"].append({
                    "file": rel_name,
                    "reason": (
                        "har_requires_dedicated_body_stripping"
                        if is_har
                        else "binary_requires_manual_visual_redaction"
                    ),
                    "sha256": sha256_bytes(raw),
                    "size": len(raw),
                })
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                report["blocked"].append({
                    "file": rel_name,
                    "reason": "non_utf8_requires_manual_review",
                    "sha256": sha256_bytes(raw),
                    "size": len(raw),
                })
                continue
            cleaned, counts = redact_text(text)
            encoded = cleaned.encode("utf-8")
            _write_at(active_output_fd, rel_name, encoded, published_outputs)
            for key, value in counts.items():
                report["totals"][key] = report["totals"].get(key, 0) + value
            report["files"].append({
                "source": rel_name,
                "output": rel_name,
                "source_sha256": sha256_bytes(raw),
                "source_size": len(raw),
                "output_sha256": sha256_bytes(encoded),
                "output_size": len(encoded),
                "redactions": counts,
            })
    finally:
        if owned_output_fd:
            os.close(active_output_fd)
    return report
