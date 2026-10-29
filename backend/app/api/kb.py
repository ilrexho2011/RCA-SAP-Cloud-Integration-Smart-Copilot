"""Knowledge Base API — generate governed artifacts + download package (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..kb import service

router = APIRouter(prefix="/api/kb", tags=["kb"])

_SCOPES = {"all", "errors", "common", "catalog"}


class GenerateRequest(BaseModel):
    scope: str = "all"


@router.post("/generate")
async def generate(req: GenerateRequest, p: Principal = Depends(current_principal),
                   settings: Settings = Depends(get_settings)) -> dict:
    scope = req.scope if req.scope in _SCOPES else "all"
    return await service.generate(settings, p.tenant_id, scope)


@router.get("/download")
async def download(p: Principal = Depends(current_principal)) -> Response:
    result = service.build_zip(p.tenant_id)
    if not result:
        raise HTTPException(404, "No package generated yet.")
    package_id, data = result
    return Response(content=data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{package_id}.zip"'})
