"""Quality gate — score a generated artifact against weighted criteria.

Adapted from the AI4BIZ gate model: structural validity, grounding (citations
present), best-practice coverage (error handling, security). A run must clear
the threshold before it may reach the write gate.
"""
from __future__ import annotations

from .validators import ValidationResult

THRESHOLD = 70  # below this = not ready to deploy


def score(validation: ValidationResult, brief: dict) -> dict:
    criteria: list[dict] = []

    def crit(name: str, weight: int, passed: bool) -> None:
        criteria.append({"name": name, "weight": weight, "passed": passed,
                         "points": weight if passed else 0})

    struct_ok = validation.ok
    crit("Structural validity", 40, struct_ok)
    crit("Grounded in patterns (citations)", 25, bool(brief.get("citations")))
    crit("Error handling defined", 20, bool(brief.get("error_handling")))
    crit("Security defined", 15, bool(brief.get("security")))

    total = sum(c["points"] for c in criteria)
    if total >= 90:
        status = "Enterprise Ready"
    elif total >= 80:
        status = "Ready with minor improvements"
    elif total >= THRESHOLD:
        status = "Conditional readiness"
    elif total >= 60:
        status = "Needs remediation"
    else:
        status = "Not ready"

    return {
        "total": total,
        "threshold": THRESHOLD,
        "passed": total >= THRESHOLD,
        "status": status,
        "criteria": criteria,
    }
