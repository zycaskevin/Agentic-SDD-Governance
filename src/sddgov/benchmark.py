from __future__ import annotations

import json
from pathlib import Path


WEIGHTS = {
    "root_cause_correct": 35,
    "minimal_fix": 20,
    "regression_test_added": 20,
    "proof_complete": 15,
}


def score(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    total = sum(weight for key, weight in WEIGHTS.items() if data.get(key) is True)
    total -= min(int(data.get("speculation_count", 0)) * 3, 15)
    total -= min(int(data.get("human_interruptions", 0)) * 5, 20)
    if data.get("sensitive_data_leak"):
        total -= 40
    return {"path": str(path), "score": max(0, total), "metrics": data}


def compare(screenshot: Path, evidence: Path) -> dict:
    baseline = score(screenshot)
    treatment = score(evidence)
    return {
        "screenshot_only": baseline,
        "evidence_driven": treatment,
        "delta": treatment["score"] - baseline["score"],
        "claim_allowed": False,
        "note": "A fixture comparison is a harness smoke test, not an empirical superiority claim.",
    }
