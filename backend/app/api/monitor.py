"""Monitor API — watch list, Ask your monitoring, JMS queue health (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..services import monitor_service

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


class AskRequest(BaseModel):
    question: str


@router.get("/flows")
async def flows(p: Principal = Depends(current_principal),
                settings: Settings = Depends(get_settings)) -> list[dict]:
    return await monitor_service.list_flows(settings, p.tenant_id)


@router.post("/watch/{iflow_id}")
async def watch(iflow_id: str, p: Principal = Depends(current_principal)) -> dict:
    return await monitor_service.watch(p.tenant_id, iflow_id)


@router.delete("/watch/{iflow_id}")
async def unwatch(iflow_id: str, p: Principal = Depends(current_principal)) -> dict:
    return await monitor_service.unwatch(p.tenant_id, iflow_id)


@router.get("/queues")
async def queues(p: Principal = Depends(current_principal),
                 settings: Settings = Depends(get_settings)) -> list[dict]:
    return await monitor_service.queues(settings, p.tenant_id)


@router.get("/queues-overview")
async def queues_overview(p: Principal = Depends(current_principal),
                          settings: Settings = Depends(get_settings)) -> dict:
    return await monitor_service.queues_overview(settings, p.tenant_id)


@router.get("/system/{kind}")
async def system_detail(kind: str, p: Principal = Depends(current_principal),
                        settings: Settings = Depends(get_settings)) -> dict:
    return await monitor_service.system_detail(settings, p.tenant_id, kind.upper())


@router.post("/ask")
async def ask(req: AskRequest, p: Principal = Depends(current_principal),
              settings: Settings = Depends(get_settings)) -> dict:
    return await monitor_service.ask(settings, p.tenant_id, req.question)
