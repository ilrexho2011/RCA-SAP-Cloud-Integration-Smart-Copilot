"""Settings API — CPI connection, AI engine, email (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..models.schemas import (
    AiEngineInfo,
    AiEngineTestResult,
    AiEngineUpdate,
    ConnectionInfo,
    ConnectionTestResult,
    ConnectionUpdate,
    EmailAlertsInfo,
    EmailAlertsUpdate,
    EmailTestResult,
    SourceInfo,
    SourceTestResult,
    SourceUpdate,
)
from ..services import monitoring_service, settings_service

_KINDS = {"APIM", "AEM"}


def _kind(kind: str) -> str:
    k = kind.upper()
    if k not in _KINDS:
        raise HTTPException(404, "unknown source kind")
    return k

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/connection", response_model=ConnectionInfo)
async def get_connection(p: Principal = Depends(current_principal),
                         settings: Settings = Depends(get_settings)) -> ConnectionInfo:
    return await settings_service.get_connection(settings, p.tenant_id)


@router.put("/connection", response_model=ConnectionInfo)
async def save_connection(update: ConnectionUpdate, p: Principal = Depends(current_principal),
                          settings: Settings = Depends(get_settings)) -> ConnectionInfo:
    return await settings_service.save_connection(settings, p.tenant_id, update)


@router.post("/connection/test", response_model=ConnectionTestResult)
async def test_connection(p: Principal = Depends(current_principal),
                          settings: Settings = Depends(get_settings)) -> ConnectionTestResult:
    return await monitoring_service.test_connection(settings, p.tenant_id)


@router.post("/connection/mode/{mode}", response_model=ConnectionInfo)
async def switch_mode(mode: str, p: Principal = Depends(current_principal),
                      settings: Settings = Depends(get_settings)) -> ConnectionInfo:
    return await settings_service.switch_mode(settings, p.tenant_id, mode)


@router.get("/ai-engine", response_model=AiEngineInfo)
async def get_ai_engine(p: Principal = Depends(current_principal)) -> AiEngineInfo:
    return await settings_service.get_ai_engine(p.tenant_id)


@router.put("/ai-engine", response_model=AiEngineInfo)
async def save_ai_engine(update: AiEngineUpdate, p: Principal = Depends(current_principal),
                         settings: Settings = Depends(get_settings)) -> AiEngineInfo:
    return await settings_service.save_ai_engine(settings, p.tenant_id, update)


@router.post("/ai-engine/test", response_model=AiEngineTestResult)
async def test_ai_engine(p: Principal = Depends(current_principal),
                         settings: Settings = Depends(get_settings)) -> AiEngineTestResult:
    return await settings_service.test_ai_engine(settings, p.tenant_id)


@router.get("/ai-engine/models")
async def list_models(p: Principal = Depends(current_principal),
                      settings: Settings = Depends(get_settings)) -> dict:
    return await settings_service.list_models(settings, p.tenant_id)


@router.get("/email", response_model=EmailAlertsInfo)
async def get_email(p: Principal = Depends(current_principal)) -> EmailAlertsInfo:
    return await settings_service.get_email(p.tenant_id)


@router.put("/email", response_model=EmailAlertsInfo)
async def save_email(update: EmailAlertsUpdate, p: Principal = Depends(current_principal),
                     settings: Settings = Depends(get_settings)) -> EmailAlertsInfo:
    return await settings_service.save_email(settings, p.tenant_id, update)


@router.post("/email/test", response_model=EmailTestResult)
async def test_email(p: Principal = Depends(current_principal)) -> EmailTestResult:
    return await settings_service.test_email(p.tenant_id)


@router.get("/source/{kind}", response_model=SourceInfo)
async def get_source(kind: str, p: Principal = Depends(current_principal)) -> SourceInfo:
    return await settings_service.get_source(p.tenant_id, _kind(kind))


@router.put("/source/{kind}", response_model=SourceInfo)
async def save_source(kind: str, update: SourceUpdate, p: Principal = Depends(current_principal),
                      settings: Settings = Depends(get_settings)) -> SourceInfo:
    return await settings_service.save_source(settings, p.tenant_id, _kind(kind), update)


@router.post("/source/{kind}/test", response_model=SourceTestResult)
async def test_source(kind: str, p: Principal = Depends(current_principal),
                      settings: Settings = Depends(get_settings)) -> SourceTestResult:
    return await settings_service.test_source(settings, p.tenant_id, _kind(kind))
