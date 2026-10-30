"""Registration and login."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db.models import Tenant, User
from . import security


async def register(session: AsyncSession, settings: Settings, email: str, password: str) -> dict:
    email = email.strip().lower()
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    exists = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if exists:
        raise ValueError("An account with this email already exists.")
    # Each new account gets its own tenant (workspace). Multi-user invites: later.
    tenant = Tenant(name=f"{email.split('@')[0]}'s workspace")
    session.add(tenant)
    await session.flush()
    user = User(tenant_id=tenant.id, email=email,
                password_hash=security.hash_password(password), role="admin")
    session.add(user)
    await session.commit()
    token = security.create_token(settings, user_id=user.id, tenant_id=tenant.id, role=user.role)
    return {"token": token, "email": email, "role": user.role, "tenant_id": tenant.id}


async def login(session: AsyncSession, settings: Settings, email: str, password: str) -> dict:
    email = email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not security.verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password.")
    token = security.create_token(settings, user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    return {"token": token, "email": user.email, "role": user.role, "tenant_id": user.tenant_id}


async def user_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count(User.id)))).scalar_one()
