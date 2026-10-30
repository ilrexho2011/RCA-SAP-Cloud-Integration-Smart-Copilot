"""AI4BIZ/QDKEP knowledge schema helpers: metadata order, sections, filenames.

Follows the fundamental policies (knowledge_schema_standard, BM25 authoring,
interface inventory) so generated artifacts pass the deterministic validator and
are ready for QDKEP ingestion.
"""
from __future__ import annotations

import re

MANDATORY_METADATA = ["environment", "customer_id", "system_id", "sap_sid",
                      "artifact_type", "object_name", "priority"]

RUNBOOK_SECTIONS = [
    "PURPOSE", "BUSINESS CONTEXT", "TECHNICAL LANDSCAPE", "MONITORING AND MPL EVIDENCE",
    "ERROR SIGNATURE", "KNOWN ROOT CAUSES", "PREREQUISITES FOR INVESTIGATION",
    "DIAGNOSIS STEPS", "RECOVERY STEPS", "ESCALATION CRITERIA", "POST-FIX VALIDATION",
]
KEDB_SECTIONS = ["ERROR PATTERN", "SYMPTOMS", "IMPACT", "ROOT CAUSE",
                 "CONFIRMING EVIDENCE", "RESOLUTION SUMMARY", "VALIDATION"]


def sanitize_customer(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "RCA").upper()) or "RCA"


def sanitize_system(s: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "-", (s or "CPI").upper()).strip("-") or "CPI"


def error_code(signature: str) -> str:
    """Uppercased [A-Z0-9_] token for the filename error segment."""
    code = re.sub(r"[^A-Za-z0-9]+", "_", (signature or "GENERIC_ERROR")).strip("_").upper()
    return code or "GENERIC_ERROR"


def canonical_phrase(signature: str) -> str:
    """Human-readable canonical error phrase for titles/body (repeated for BM25)."""
    return error_code(signature).replace("_", " ").title()


def kb_filename(kind: str, customer: str, system: str, signature: str, priority: str, version: int = 1) -> str:
    prefix = "KB" if kind == "kedb" else "RB"
    p = priority if re.fullmatch(r"P[1-4]", priority or "") else "P3"
    return f"{prefix}_{sanitize_customer(customer)}_{sanitize_system(system)}_{error_code(signature)}_{p}_v{version}.md"


def doc_filename(customer: str, system: str, name: str, version: int = 1) -> str:
    n = re.sub(r"[^A-Za-z0-9]+", "_", name or "OBJECT").strip("_").upper() or "OBJECT"
    return f"DOC_{sanitize_customer(customer)}_{sanitize_system(system)}_{n}_v{version}.md"


def metadata_block(md: dict) -> str:
    """Render metadata as stable 'key: value' lines (mandatory first, in order)."""
    lines = [f"{k}: {md[k]}" for k in MANDATORY_METADATA if md.get(k) is not None]
    extra_order = ["domain", "technology", "interface_name", "integration_flow_id",
                   "integration_flow_name", "package_name", "review_status", "version",
                   "source_file", "created_at", "updated_at"]
    for k in extra_order:
        if md.get(k) is not None:
            lines.append(f"{k}: {md[k]}")
    return "\n".join(lines)
