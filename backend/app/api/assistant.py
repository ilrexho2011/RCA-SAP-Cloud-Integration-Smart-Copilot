"""AI Assistant API — grounded chat (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..services import assistant_service

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
async def chat(req: ChatRequest, p: Principal = Depends(current_principal),
               settings: Settings = Depends(get_settings)) -> dict:
    return await assistant_service.chat(settings, p.tenant_id, [m.model_dump() for m in req.messages])
