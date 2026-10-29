"""iFlows API — browse packages/iFlows and Explain (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..iflow import explain as explain_mod
from ..iflow.parser import extract_iflw_from_zip, extract_scripts_from_zip, parse_iflow_xml
from ..llm.provider import get_provider
from ..models.schemas import ExplainResult
from ..orchestrator import agents
from ..services.connection import resolve_connector

router = APIRouter(prefix="/api/iflows", tags=["iflows"])


@router.get("/packages")
async def packages(p: Principal = Depends(current_principal),
                   settings: Settings = Depends(get_settings)) -> list[dict]:
    conn = await resolve_connector(settings, p.tenant_id)
    if not hasattr(conn, "integration_packages"):
        return []
    try:
        return await conn.integration_packages()
    except Exception as e:  # noqa: BLE001 — surface the real reason (often an OAuth scope)
        raise HTTPException(502, str(e))


@router.get("/packages/{package_id}/iflows")
async def package_iflows(package_id: str, p: Principal = Depends(current_principal),
                         settings: Settings = Depends(get_settings)) -> list[dict]:
    conn = await resolve_connector(settings, p.tenant_id)
    if not hasattr(conn, "package_iflows"):
        return []
    try:
        return await conn.package_iflows(package_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@router.post("/explain-zip", response_model=ExplainResult)
async def explain_zip(file: UploadFile = File(...), p: Principal = Depends(current_principal),
                      settings: Settings = Depends(get_settings)) -> ExplainResult:
    data = await file.read()
    try:
        xml = extract_iflw_from_zip(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not read iFlow from ZIP: {e}")
    model = parse_iflow_xml(xml)
    scripts = extract_scripts_from_zip(data)
    result = await explain_mod.explain(await get_provider(settings, p.tenant_id), model, scripts)
    return ExplainResult(source="zip", **result)


@router.post("/explain/{package_id}/{iflow_id}", response_model=ExplainResult)
async def explain_tenant(package_id: str, iflow_id: str, p: Principal = Depends(current_principal),
                         settings: Settings = Depends(get_settings)) -> ExplainResult:
    conn = await resolve_connector(settings, p.tenant_id)
    scripts: list[dict] = []
    if hasattr(conn, "download_iflow") and getattr(conn, "live", False):
        try:
            data = await conn.download_iflow(iflow_id)
            xml = extract_iflw_from_zip(data)
            scripts = extract_scripts_from_zip(data)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"Could not fetch iFlow from tenant: {e}")
        source = "tenant"
    else:
        xml = agents.generate_iflow(
            iflow_id, iflow_id,
            {"sender": "HTTPS", "receiver": "OData", "needs_mapping": True, "needs_groovy": True},
            {"steps": ["Receive via HTTPS sender adapter", "Message Mapping: source → target",
                       "Groovy script: enrichment", "Send to OData receiver"],
             "error_handling": "yes", "security": "OAuth2"},
        )
        source = "demo"
    model = parse_iflow_xml(xml)
    result = await explain_mod.explain(await get_provider(settings, p.tenant_id), model, scripts)
    return ExplainResult(source=source, **result)


@router.get("/runtime-status")
async def runtime_status(p: Principal = Depends(current_principal),
                         settings: Settings = Depends(get_settings)) -> dict:
    """Map of iFlow id → deployment status (STARTED/ERROR/…), from runtime artifacts.
    Design-time ids match runtime ids on CPI, so the iFlows table can show
    DEPLOYED / NOT_DEPLOYED per row."""
    conn = await resolve_connector(settings, p.tenant_id)
    if not hasattr(conn, "runtime_artifacts"):
        return {}
    try:
        arts = await conn.runtime_artifacts()
    except Exception:  # noqa: BLE001 — status is best-effort, never blocks the list
        return {}
    return {a.get("id", ""): (a.get("status") or "").upper() for a in arts if a.get("id")}
