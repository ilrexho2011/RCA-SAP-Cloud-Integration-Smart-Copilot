"""Knowledge Base generation service (tenant-scoped).

Gathers the live inventory (iFlows), MPL error patterns and — where available —
parsed iFlow models, then emits governed Markdown artifacts + JSON metadata as a
package ready for QDKEP ingestion. A deterministic readiness score is computed
with the vendored validator.
"""
from __future__ import annotations

import io
import json
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from ..iflow.parser import extract_iflw_from_zip, parse_iflow_xml
from ..services.connection import resolve_connector
from ..services import monitoring_service
from . import generator, package_validator as pv, schema

GENERATOR_VERSION = "rca-smart-copilot-kb/0.1"
MAX_CATALOG = 25
MAX_DEEP_PARSE = 8

_PACKAGES: dict[str, dict] = {}   # tenant_id -> last generated package

# Canonical global CPI failure patterns (used for the 'common' scope).
_COMMON = [
    {"signature": "HTTP_401_UNAUTHORIZED", "exception": "UNAUTHORIZED", "interface": "CPI_Receiver_Call",
     "error": "HTTP 401 Unauthorized on receiver call — invalid or expired credentials", "priority": "P2"},
    {"signature": "HTTP_429_RATE_LIMIT", "exception": "RATE_LIMIT", "interface": "CPI_Receiver_Call",
     "error": "HTTP 429 receiver throttled — API rate limit exceeded", "priority": "P2"},
    {"signature": "CONNECTION_TIMEOUT", "exception": "TIMEOUT", "interface": "CPI_Receiver_Call",
     "error": "Connection timeout to backend — no response within the configured timeout", "priority": "P2"},
    {"signature": "MAPPING_ERROR", "exception": "MAPPING", "interface": "CPI_Message_Mapping",
     "error": "Message mapping failure — source structure did not match target XSD", "priority": "P3"},
    {"signature": "CSRF_TOKEN_FAILURE", "exception": "CSRF", "interface": "CPI_OData_Receiver",
     "error": "CSRF token validation failed on OData receiver (HTTP 403)", "priority": "P2"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _priority_for(signature: str) -> str:
    up = signature.upper()
    if any(k in up for k in ("CONN", "SYSFAIL", "TIMEOUT", "401", "403", "500")):
        return "P2"
    return "P3"


def _patterns_from_failures(failed: list) -> list[dict]:
    groups: dict[str, dict] = {}
    for m in failed:                       # FailedMessage pydantic objects
        sig = (m.interface or "GENERIC_ERROR")
        g = groups.setdefault(sig, {"signature": sig, "interface": m.interface or "",
                                    "exception": m.exception or "", "error": m.error or "",
                                    "count": 0, "priority": _priority_for(sig)})
        g["count"] += 1
    return list(groups.values())


async def _iflow_models(settings: Settings, tenant_id: str) -> list[dict]:
    conn = await resolve_connector(settings, tenant_id)
    arts = await conn.runtime_artifacts() if hasattr(conn, "runtime_artifacts") else []
    models: list[dict] = []
    live = getattr(conn, "live", False)
    for i, a in enumerate(arts[:MAX_CATALOG]):
        name = a.get("name") or a.get("id", "iFlow")
        model = {"name": name, "id": a.get("id", ""), "status": a.get("status", ""),
                 "sender_adapter": "", "receiver_adapter": "", "steps": [],
                 "step_count": 0, "has_error_handling": False}
        if live and i < MAX_DEEP_PARSE and hasattr(conn, "download_iflow"):
            try:
                xml = extract_iflw_from_zip(await conn.download_iflow(a.get("id", "")))
                parsed = parse_iflow_xml(xml)
                model = parsed.as_dict()
                model["id"] = a.get("id", "")
                model["status"] = a.get("status", "")
            except Exception:  # noqa: BLE001
                pass
        models.append(model)
    return models


def _readiness(docs: list[dict]) -> dict:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for d in docs:
            (root / d["filename"]).write_text(d["content"], encoding="utf-8")
        _, files, _ = pv.iter_markdown_files(root)
        results = [pv.validate_document(root, f) for f in files]
        summary = pv.package_summary(results, root)
    return {"score": summary["estimated_static_package_score"], "status": summary["status"],
            "note": summary["note"],
            "documents": [{"file_name": d["file_name"], "score": d["estimated_static_score"],
                           "status": d["status"], "issues": len(d["issues"])} for d in summary["documents"]]}


async def generate(settings: Settings, tenant_id: str, scope: str) -> dict:
    ov = await monitoring_service.get_overview(settings, tenant_id)
    sys0 = ov.systems[0] if ov.systems else None
    ctx = {"environment": ov.source, "customer_id": "RCA",
           "system_id": sys0.sap_sid + "-RCA" if sys0 else "CPI-RCA",
           "sap_sid": (sys0.sap_sid if sys0 else "CPI"), "domain": "CPI",
           "technology": "SAP CPI", "package_name": "RCA_KB"}

    docs: list[dict] = []

    def add(kind: str, filename: str, content: str, md: dict):
        docs.append({"kind": kind, "filename": filename, "content": content, "metadata": md})

    if scope in ("errors", "all"):
        for p in _patterns_from_failures(ov.failed_messages):
            kb, kmd = generator.render_kedb(p, ctx)
            add("kedb", schema.kb_filename("kedb", ctx["customer_id"], ctx["sap_sid"], p["signature"], p["priority"]), kb, kmd)
            rb, rmd = generator.render_runbook(p, ctx)
            add("runbook", schema.kb_filename("runbook", ctx["customer_id"], ctx["sap_sid"], p["signature"], p["priority"]), rb, rmd)

    if scope in ("common", "all"):
        for p in _COMMON:
            kb, kmd = generator.render_kedb(p, ctx)
            add("kedb", schema.kb_filename("kedb", ctx["customer_id"], "CPI", p["signature"], p["priority"]), kb, kmd)
            rb, rmd = generator.render_runbook(p, ctx)
            add("runbook", schema.kb_filename("runbook", ctx["customer_id"], "CPI", p["signature"], p["priority"]), rb, rmd)

    if scope in ("catalog", "all"):
        for model in await _iflow_models(settings, tenant_id):
            body, md = generator.render_catalog(model, ctx)
            add("interface_inventory", schema.doc_filename(ctx["customer_id"], ctx["sap_sid"], model["name"]), body, md)

    package_id = f"RCA_KB_{uuid.uuid4().hex[:8]}"
    manifest = {
        "package_id": package_id, "run_id": uuid.uuid4().hex[:12],
        "source_system": ctx["sap_sid"], "generated_at": _now(),
        "generator_version": GENERATOR_VERSION, "scope": scope,
        "counts": {"total": len(docs),
                   "kedb": sum(1 for d in docs if d["kind"] == "kedb"),
                   "runbook": sum(1 for d in docs if d["kind"] == "runbook"),
                   "interface_inventory": sum(1 for d in docs if d["kind"] == "interface_inventory")},
        "files": [d["filename"] for d in docs],
    }
    readiness = _readiness(docs) if docs else {"score": 0, "status": "Not ready", "documents": []}

    _PACKAGES[tenant_id] = {"manifest": manifest, "docs": docs}
    return {"manifest": manifest, "readiness": readiness,
            "docs": [{"filename": d["filename"], "kind": d["kind"], "content": d["content"]} for d in docs]}


def build_zip(tenant_id: str) -> tuple[str, bytes] | None:
    pkg = _PACKAGES.get(tenant_id)
    if not pkg:
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(pkg["manifest"], indent=2))
        for d in pkg["docs"]:
            zf.writestr(d["filename"], d["content"])
            zf.writestr(d["filename"].rsplit(".", 1)[0] + ".json", json.dumps(d["metadata"], indent=2))
    return pkg["manifest"]["package_id"], buf.getvalue()
