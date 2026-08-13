from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern[str]
    replacement: str


RULES: tuple[Rule, ...] = (
    Rule("private-key", re.compile(r"-----BEGIN [^-]*(?:PRIVATE KEY|OPENSSH PRIVATE KEY)-----.*?-----END [^-]*(?:PRIVATE KEY|OPENSSH PRIVATE KEY)-----", re.I | re.S), "[REDACTED_PRIVATE_KEY]"),
    Rule("authorization", re.compile(r"(?im)^(authorization\s*:\s*)(?:bearer\s+)?[^\r\n]+"), r"\1[REDACTED_AUTHORIZATION]"),
    Rule("cookie", re.compile(r"(?im)^((?:set-)?cookie\s*:\s*)[^\r\n]+"), r"\1[REDACTED_COOKIE]"),
    Rule("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "[REDACTED_JWT]"),
    Rule("password", re.compile(r'''(?i)((?:"|')?(?:[A-Z0-9]+_)*(?:password|passwd)(?:"|')?\s*[=:]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)'''), r"\1[REDACTED_PASSWORD]"),
    Rule("secret-field", re.compile(r'''(?i)((?:"|')?(?:[A-Z0-9]+[_-])*(?:secret(?:[_-]?key)?|api[_-]?key|access[_-]?(?:token|key)|refresh[_-]?token|client[_-]?secret)(?:[_-][A-Z0-9]+)*(?:"|')?\s*[=:]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)'''), r"\1[REDACTED_SECRET]"),
    Rule("patient-identifier", re.compile(r'''(?i)((?:"|')?\bpatient[_-]?(?:id|identifier)\b(?:"|')?\s*[=:]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)'''), r"\1[REDACTED_PATIENT_IDENTIFIER]"),
    Rule("customer-identifier", re.compile(r'''(?i)((?:"|')?\bcustomer[_-]?(?:id|identifier)\b(?:"|')?\s*[=:]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;"']+)'''), r"\1[REDACTED_CUSTOMER_IDENTIFIER]"),
    Rule("email", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[REDACTED_EMAIL]"),
    Rule("phone", re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)"), "[REDACTED_PHONE_OR_NUMBER]"),
    Rule("card-like", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"), "[REDACTED_CARD_OR_NUMBER]"),
)


TEXT_SUFFIXES = {
    ".txt", ".log", ".json", ".jsonl", ".yaml", ".yml", ".xml", ".md",
    ".har", ".csv", ".tsv", ".html", ".js", ".ts", ".dart", ".sh",
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
    return output, counts


def redact_files(files: Iterable[Path], output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": "1.0", "files": [], "blocked": [], "totals": {}}
    for source in files:
        rel_name = source.name
        raw = source.read_bytes()
        if source.suffix.lower() not in TEXT_SUFFIXES:
            report["blocked"].append({
                "file": rel_name,
                "reason": "binary_requires_manual_visual_redaction",
                "sha256": sha256_bytes(raw),
            })
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            report["blocked"].append({
                "file": rel_name,
                "reason": "non_utf8_requires_manual_review",
                "sha256": sha256_bytes(raw),
            })
            continue
        cleaned, counts = redact_text(text)
        destination = output_dir / rel_name
        destination.write_text(cleaned, encoding="utf-8")
        for key, value in counts.items():
            report["totals"][key] = report["totals"].get(key, 0) + value
        report["files"].append({
            "source": rel_name,
            "output": rel_name,
            "source_sha256": sha256_bytes(raw),
            "output_sha256": sha256_bytes(cleaned.encode("utf-8")),
            "redactions": counts,
        })
    return report


def write_report(report: dict, path: Path) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
