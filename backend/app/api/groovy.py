"""Groovy API (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..models.schemas import GroovyRequest, GroovyResult
from ..services import groovy_service

router = APIRouter(prefix="/api/groovy", tags=["groovy"])


@router.post("/generate", response_model=GroovyResult)
async def generate(req: GroovyRequest, p: Principal = Depends(current_principal),
                   settings: Settings = Depends(get_settings)) -> GroovyResult:
    result = await groovy_service.generate_script(settings, p.tenant_id, req.description)
    return GroovyResult(**result)
