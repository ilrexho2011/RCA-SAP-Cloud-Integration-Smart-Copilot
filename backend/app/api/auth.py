"""Auth API: register, login, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import service
from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..db.base import get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str


class AuthResult(BaseModel):
    token: str
    email: str
    role: str
    tenant_id: str


@router.post("/register", response_model=AuthResult)
async def register(body: Credentials, settings: Settings = Depends(get_settings),
                   session: AsyncSession = Depends(get_session)) -> AuthResult:
    try:
        return AuthResult(**await service.register(session, settings, body.email, body.password))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/login", response_model=AuthResult)
async def login(body: Credentials, settings: Settings = Depends(get_settings),
                session: AsyncSession = Depends(get_session)) -> AuthResult:
    try:
        return AuthResult(**await service.login(session, settings, body.email, body.password))
    except ValueError as e:
        raise HTTPException(401, str(e))


@router.get("/me")
async def me(p: Principal = Depends(current_principal)) -> dict:
    return {"email": p.email, "role": p.role, "tenant_id": p.tenant_id}
