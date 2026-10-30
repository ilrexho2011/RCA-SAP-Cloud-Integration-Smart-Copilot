"""Auth dependencies: current user, tenant scope, role guard."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..db.base import get_session
from ..db.models import User
from . import security


@dataclass
class Principal:
    user_id: str
    tenant_id: str
    role: str
    email: str


async def current_principal(
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = security.decode_token(settings, token)
    except Exception:  # noqa: BLE001
        raise HTTPException(401, "Invalid or expired token")
    user = (await session.execute(select(User).where(User.id == payload.get("sub")))).scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User no longer exists")
    return Principal(user_id=user.id, tenant_id=user.tenant_id, role=user.role, email=user.email)


def require_role(*roles: str):
    async def _guard(p: Principal = Depends(current_principal)) -> Principal:
        if p.role not in roles:
            raise HTTPException(403, "Insufficient role")
        return p
    return _guard
