from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import stat
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .fs_security import remove_owned_at


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
LOCAL_USER_PATH_PATTERN = re.compile(
    r'''(?ix)(?<![A-Z0-9])(?:'''
    r'''["'](?:/(?:home|Users)/|/(?:private/)?tmp(?=$|/|["'])|/var/folders/|[A-Z]:(?:\\{1,2}|/)Users(?:\\{1,2}|/))[^"'\r\n]*["']'''
    r'''|/(?:home|Users)/[^\r\n:;,'"]*'''
    r'''|/(?:private/)?tmp(?=$|/|[\s:;,'"])(?:/[^\r\n:;,'"]*)?'''
    r'''|/var/folders/[^\r\n:;,'"]*'''
    r'''|[A-Z]:(?:\\{1,2}|/)Users(?:\\{1,2}|/)[^\r\n:;,'"]*'''
    r''')'''
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
    Rule("email", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[REDACTED_EMAIL]"),
    Rule("phone", re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)"), "[REDACTED_PHONE_OR_NUMBER]"),
    Rule("card-like", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"), "[REDACTED_CARD_OR_NUMBER]"),
    Rule("local-path", LOCAL_USER_PATH_PATTERN, "[REDACTED_LOCAL_PATH]"),
)

STREAM_RULES: tuple[Rule, ...] = tuple(
    rule for rule in RULES if rule.rule_id != "private-key"
)


TEXT_SUFFIXES = {
    ".txt", ".log", ".json", ".jsonl", ".yaml", ".yml", ".xml", ".md",
    ".csv", ".tsv", ".html", ".js", ".ts", ".dart", ".sh",
}

MAX_REDACTION_FILE_BYTES = 10 * 1024 * 1024
MAX_LOGICAL_LINE_CHARACTERS = 1024 * 1024
STREAM_CHUNK_BYTES = 64 * 1024
MAX_PRIVATE_KEY_MARKER_CHARACTERS = 4096
PRIVATE_KEY_BEGIN = re.compile(
    r"-----BEGIN [^-]*(?:PRIVATE KEY|OPENSSH PRIVATE KEY)-----", re.I
)
PRIVATE_KEY_END = re.compile(
    r"-----END [^-]*(?:PRIVATE KEY|OPENSSH PRIVATE KEY)-----", re.I
)
PRIVATE_KEY_MARKER_PREFIX = re.compile(r"-----BEGIN|-----END", re.I)
PRIVATE_KEY_MARKER_LITERALS = ("-----begin", "-----end")


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
    if LOCAL_USER_PATH_PATTERN.search(output):
        raise ValueError("unredacted absolute user workspace path")
    return output, counts


def _merge_counts(total: dict[str, int], added: dict[str, int]) -> None:
    for key, value in added.items():
        total[key] = total.get(key, 0) + value


class _StreamingTextRedactor:
    def __init__(self) -> None:
        self.in_private_key = False
        self.marker_fragment = ""
        self.counts: dict[str, int] = {}

    def _hold_incomplete_marker(self, text: str, prefix: str) -> tuple[str, str]:
        marker = -1
        for match in PRIVATE_KEY_MARKER_PREFIX.finditer(text):
            if match.group(0).casefold() == prefix.casefold():
                marker = match.start()
        if marker < 0:
            logical = text.removesuffix("\n").removesuffix("\r")
            for literal in PRIVATE_KEY_MARKER_LITERALS:
                for length in range(min(len(literal) - 1, len(logical)), 0, -1):
                    candidate_start = len(logical) - length
                    if (
                        logical[-length:].lower() == literal[:length]
                        and (
                            candidate_start == 0
                            or logical[candidate_start - 1] != "-"
                        )
                    ):
                        marker = len(logical) - length
                        break
                if marker >= 0:
                    break
            if marker < 0:
                return text, ""
        elif "-----" in text[marker + len(prefix) :]:
            return text, ""
        fragment = text[marker:]
        if len(fragment) > MAX_PRIVATE_KEY_MARKER_CHARACTERS:
            raise ValueError("private key marker exceeds the streaming safety limit")
        return text[:marker], fragment

    def _private_keys(self, text: str) -> str:
        output: list[str] = []
        carried = self.marker_fragment
        self.marker_fragment = ""
        if carried.endswith(("\n", "\r")):
            logical = carried.rstrip("\r\n")
            if any(
                literal in logical.lower()
                for literal in PRIVATE_KEY_MARKER_LITERALS
            ):
                remaining = carried + text
            else:
                for literal in PRIVATE_KEY_MARKER_LITERALS:
                    probe = (logical + text)[: len(literal)].lower()
                    if literal.startswith(probe):
                        raise ValueError(
                            "private key marker is split across a logical-line boundary"
                        )
                output.append(carried)
                remaining = text
        else:
            remaining = carried + text
        while remaining:
            if self.in_private_key:
                end = PRIVATE_KEY_END.search(remaining)
                if end is None:
                    _, self.marker_fragment = self._hold_incomplete_marker(
                        remaining, "-----END"
                    )
                    return "".join(output)
                self.in_private_key = False
                remaining = remaining[end.end() :]
                continue
            begin = PRIVATE_KEY_BEGIN.search(remaining)
            if begin is None:
                safe, self.marker_fragment = self._hold_incomplete_marker(
                    remaining, "-----BEGIN"
                )
                output.append(safe)
                break
            output.append(remaining[: begin.start()])
            output.append("[REDACTED_PRIVATE_KEY]")
            self.counts["private-key"] = self.counts.get("private-key", 0) + 1
            remaining = remaining[begin.end() :]
            end = PRIVATE_KEY_END.search(remaining)
            if end is None:
                self.in_private_key = True
                break
            remaining = remaining[end.end() :]
        return "".join(output)

    def _apply_stream_rules(self, text: str) -> str:
        cleaned = text
        counts: dict[str, int] = {}
        for rule in STREAM_RULES:
            cleaned, count = rule.pattern.subn(rule.replacement, cleaned)
            if count:
                counts[rule.rule_id] = count
        if PROVIDER_CREDENTIAL_PATTERN.search(cleaned):
            raise ValueError("unredacted known provider credential identifier")
        if LOCAL_USER_PATH_PATTERN.search(cleaned):
            raise ValueError("unredacted absolute user workspace path")
        _merge_counts(self.counts, counts)
        return cleaned

    def redact_line(self, line: str) -> str:
        return self._apply_stream_rules(self._private_keys(line))

    def finish(self) -> str:
        if self.in_private_key:
            raise ValueError("unterminated private key block in redaction source")
        trailing = self.marker_fragment
        self.marker_fragment = ""
        if not trailing:
            return ""
        return self._apply_stream_rules(trailing)


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


def _validate_published_identity(
    directory_fd: int, name: str, temporary_metadata: os.stat_result
) -> tuple[int, int]:
    published = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    identity = (temporary_metadata.st_dev, temporary_metadata.st_ino)
    if (
        not stat.S_ISREG(published.st_mode)
        or published.st_nlink != 1
        or (published.st_dev, published.st_ino) != identity
    ):
        raise ValueError(f"redaction destination changed during publish: {name}")
    return identity


def _reconcile_failed_publication(
    directory_fd: int, name: str, expected_identity: tuple[int, int]
) -> None:
    """Remove our generation while preserving any later writer at ``name``."""
    remove_owned_at(
        directory_fd,
        name,
        expected_identity,
        "redaction destination",
    )


def _stream_text_at(
    source_descriptor: int,
    output_directory_fd: int,
    name: str,
    published_outputs: dict[str, tuple[int, int]] | None,
) -> tuple[str, int, str, int, dict[str, int]]:
    try:
        existing = os.stat(name, dir_fd=output_directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        existing = None
    if existing is not None and stat.S_ISLNK(existing.st_mode):
        raise ValueError(f"redaction destination must not be a symlink: {name}")
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise ValueError(f"redaction destination must be a regular file: {name}")

    temporary = f".{name}.{secrets.token_hex(16)}.tmp"
    output_descriptor = -1
    source_digest = hashlib.sha256()
    output_digest = hashlib.sha256()
    source_size = 0
    output_size = 0
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    pending = ""
    redactor = _StreamingTextRedactor()
    try:
        output_descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=output_directory_fd,
        )

        def publish_text(value: str) -> None:
            nonlocal output_size
            encoded = value.encode("utf-8")
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(output_descriptor, remaining)
                if written <= 0:
                    raise OSError("redaction output write made no progress")
                remaining = remaining[written:]
            output_digest.update(encoded)
            output_size += len(encoded)

        while True:
            chunk = os.read(source_descriptor, STREAM_CHUNK_BYTES)
            if not chunk:
                break
            source_size += len(chunk)
            if source_size > MAX_REDACTION_FILE_BYTES:
                raise ValueError(
                    f"redaction source exceeds {MAX_REDACTION_FILE_BYTES} bytes: {name}; collect a bounded excerpt or summary"
                )
            source_digest.update(chunk)
            pending += decoder.decode(chunk, final=False)
            while True:
                newline = pending.find("\n")
                if newline < 0:
                    if len(pending) > MAX_LOGICAL_LINE_CHARACTERS:
                        raise ValueError(
                            f"redaction source has a logical line exceeding {MAX_LOGICAL_LINE_CHARACTERS} characters: {name}"
                        )
                    break
                line = pending[: newline + 1]
                pending = pending[newline + 1 :]
                if len(line) - 1 > MAX_LOGICAL_LINE_CHARACTERS:
                    raise ValueError(
                        f"redaction source has a logical line exceeding {MAX_LOGICAL_LINE_CHARACTERS} characters: {name}"
                    )
                publish_text(redactor.redact_line(line))
        pending += decoder.decode(b"", final=True)
        if len(pending) > MAX_LOGICAL_LINE_CHARACTERS:
            raise ValueError(
                f"redaction source has a logical line exceeding {MAX_LOGICAL_LINE_CHARACTERS} characters: {name}"
            )
        if pending:
            publish_text(redactor.redact_line(pending))
        publish_text(redactor.finish())
        os.fsync(output_descriptor)
        temporary_metadata = os.fstat(output_descriptor)
        os.replace(
            temporary,
            name,
            src_dir_fd=output_directory_fd,
            dst_dir_fd=output_directory_fd,
        )
        try:
            published_identity = _validate_published_identity(
                output_directory_fd, name, temporary_metadata
            )
        except BaseException as primary:
            try:
                _reconcile_failed_publication(
                    output_directory_fd,
                    name,
                    (temporary_metadata.st_dev, temporary_metadata.st_ino),
                )
            except BaseException as cleanup_error:
                raise primary from cleanup_error
            raise
        if published_outputs is not None:
            published_outputs[name] = published_identity
        os.fsync(output_directory_fd)
        return (
            source_digest.hexdigest(),
            source_size,
            output_digest.hexdigest(),
            output_size,
            redactor.counts,
        )
    finally:
        if output_descriptor >= 0:
            os.close(output_descriptor)
        try:
            os.unlink(temporary, dir_fd=output_directory_fd)
        except FileNotFoundError:
            pass


def _hash_descriptor(descriptor: int, name: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(descriptor, STREAM_CHUNK_BYTES)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_REDACTION_FILE_BYTES:
            raise ValueError(
                f"redaction source exceeds {MAX_REDACTION_FILE_BYTES} bytes: {name}; collect a bounded excerpt or summary"
            )
        digest.update(chunk)
    return digest.hexdigest(), size


def _source_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_nlink,
    )


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
            source_publications: dict[str, tuple[int, int]] = {}
            try:
                current = os.fstat(descriptor)
                if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
                    raise ValueError(
                        f"redaction source must be a non-linked regular file: {rel_name}"
                    )
                if current.st_size > MAX_REDACTION_FILE_BYTES:
                    raise ValueError(
                        f"redaction source exceeds {MAX_REDACTION_FILE_BYTES} bytes: {rel_name}; collect a bounded excerpt or summary"
                    )
                artifact_metadata = (metadata_by_name or {}).get(rel_name, {})
                is_har = (
                    artifact_metadata.get("collector") == "browser-har"
                    or artifact_metadata.get("media_type") == "application/har+json"
                    or source.suffix.lower() == ".har"
                )
                if is_har or source.suffix.lower() not in TEXT_SUFFIXES:
                    source_sha256, source_size = _hash_descriptor(descriptor, rel_name)
                    report["blocked"].append({
                        "file": rel_name,
                        "reason": (
                            "har_requires_dedicated_body_stripping"
                            if is_har
                            else "binary_requires_manual_visual_redaction"
                        ),
                        "sha256": source_sha256,
                        "size": source_size,
                    })
                else:
                    try:
                        (
                            source_sha256,
                            source_size,
                            output_sha256,
                            output_size,
                            counts,
                        ) = _stream_text_at(
                            descriptor,
                            active_output_fd,
                            rel_name,
                            source_publications,
                        )
                    except UnicodeDecodeError:
                        os.lseek(descriptor, 0, os.SEEK_SET)
                        source_sha256, source_size = _hash_descriptor(
                            descriptor, rel_name
                        )
                        report["blocked"].append({
                            "file": rel_name,
                            "reason": "non_utf8_requires_manual_review",
                            "sha256": source_sha256,
                            "size": source_size,
                        })
                    else:
                        _merge_counts(report["totals"], counts)
                        report["files"].append({
                            "source": rel_name,
                            "output": rel_name,
                            "source_sha256": source_sha256,
                            "source_size": source_size,
                            "output_sha256": output_sha256,
                            "output_size": output_size,
                            "redactions": counts,
                        })
                after = os.fstat(descriptor)
                leaf = os.stat(
                    rel_name, dir_fd=active_source_fd, follow_symlinks=False
                )
                if (
                    _source_identity(before) != _source_identity(current)
                    or _source_identity(current) != _source_identity(after)
                    or _source_identity(after) != _source_identity(leaf)
                ):
                    raise ValueError(f"redaction source changed during read: {rel_name}")
                if published_outputs is not None:
                    published_outputs.update(source_publications)
            except BaseException as primary:
                try:
                    for published_name, published_identity in source_publications.items():
                        _reconcile_failed_publication(
                            active_output_fd,
                            published_name,
                            published_identity,
                        )
                except BaseException as cleanup_error:
                    raise primary from cleanup_error
                raise
            finally:
                os.close(descriptor)
                if owned_source_fd:
                    os.close(active_source_fd)
    finally:
        if owned_output_fd:
            os.close(active_output_fd)
    return report
