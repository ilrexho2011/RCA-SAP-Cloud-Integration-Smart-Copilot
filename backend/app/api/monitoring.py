"""Monitoring API routes (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..models.schemas import ConnectionTestResult, MonitoringOverview
from ..services import monitoring_service

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/overview", response_model=MonitoringOverview)
async def overview(p: Principal = Depends(current_principal),
                   settings: Settings = Depends(get_settings)) -> MonitoringOverview:
    return await monitoring_service.get_overview(settings, p.tenant_id)


@router.get("/connection-test", response_model=ConnectionTestResult)
async def connection_test(p: Principal = Depends(current_principal),
                          settings: Settings = Depends(get_settings)) -> ConnectionTestResult:
    return await monitoring_service.test_connection(settings, p.tenant_id)
