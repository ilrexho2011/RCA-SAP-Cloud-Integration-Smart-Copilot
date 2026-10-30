"""Tenant-scoped data access. Replaces the file-based store; secrets stay
AES-256-GCM encrypted. Each function manages its own async session.
"""
from __future__ import annotations

from sqlalchemy import delete, select

from ..config import Settings
from ..security import crypto
from .base import async_session
from .models import AgentRun, AiEngine, CpiConnection, EmailConfig, IntegrationSource, WatchedFlow

SENTINEL = "__stored__"


def _mk(settings: Settings) -> str:
    return crypto.load_master_key(settings)


# ---- CPI connection ----

async def get_connection(tenant_id: str) -> CpiConnection | None:
    async with async_session() as s:
        return (await s.execute(select(CpiConnection).where(CpiConnection.tenant_id == tenant_id))).scalar_one_or_none()


async def save_connection(settings: Settings, tenant_id: str, data: dict,
                          secret: str | None, rt_secret: str | None) -> None:
    async with async_session() as s:
        row = (await s.execute(select(CpiConnection).where(CpiConnection.tenant_id == tenant_id))).scalar_one_or_none()
        if not row:
            row = CpiConnection(tenant_id=tenant_id)
            s.add(row)
        row.base_url = data.get("base_url", "").strip()
        row.token_url = data.get("token_url", "").strip()
        row.client_id = data.get("client_id", "").strip()
        row.web_ide_url = data.get("web_ide_url", "").strip()
        row.mode = data.get("mode", "live")
        row.rt_base_url = data.get("rt_base_url", "").strip()
        row.rt_token_url = data.get("rt_token_url", "").strip()
        row.rt_client_id = data.get("rt_client_id", "").strip()
        mk = _mk(settings)
        if secret and secret != SENTINEL:
            row.secret_enc = crypto.encrypt(secret, mk)
        if rt_secret and rt_secret != SENTINEL:
            row.rt_secret_enc = crypto.encrypt(rt_secret, mk)
        await s.commit()


async def set_connection_mode(tenant_id: str, mode: str) -> None:
    async with async_session() as s:
        row = (await s.execute(select(CpiConnection).where(CpiConnection.tenant_id == tenant_id))).scalar_one_or_none()
        if row:
            row.mode = mode
            await s.commit()


async def get_connection_secret(settings: Settings, tenant_id: str) -> str | None:
    row = await get_connection(tenant_id)
    return crypto.decrypt(row.secret_enc, _mk(settings)) if row and row.secret_enc else None


async def has_live_connection(tenant_id: str) -> bool:
    row = await get_connection(tenant_id)
    return bool(row and row.mode == "live" and row.base_url and row.client_id and row.secret_enc)


# ---- AI engine ----

async def get_ai(tenant_id: str) -> AiEngine | None:
    async with async_session() as s:
        return (await s.execute(select(AiEngine).where(AiEngine.tenant_id == tenant_id))).scalar_one_or_none()


async def save_ai(settings: Settings, tenant_id: str, data: dict, api_key: str | None) -> None:
    async with async_session() as s:
        row = (await s.execute(select(AiEngine).where(AiEngine.tenant_id == tenant_id))).scalar_one_or_none()
        if not row:
            row = AiEngine(tenant_id=tenant_id)
            s.add(row)
        row.provider = data.get("provider", "stub")
        row.endpoint = data.get("endpoint", "").strip()
        row.model = data.get("model", "").strip()
        if api_key and api_key != SENTINEL:
            row.key_enc = crypto.encrypt(api_key, _mk(settings))
        await s.commit()


async def get_ai_key(settings: Settings, tenant_id: str) -> str | None:
    row = await get_ai(tenant_id)
    return crypto.decrypt(row.key_enc, _mk(settings)) if row and row.key_enc else None


async def has_ai_engine(tenant_id: str) -> bool:
    row = await get_ai(tenant_id)
    return bool(row and row.provider and row.provider != "stub" and row.key_enc)


# ---- Email ----

async def get_email(tenant_id: str) -> EmailConfig | None:
    async with async_session() as s:
        return (await s.execute(select(EmailConfig).where(EmailConfig.tenant_id == tenant_id))).scalar_one_or_none()


async def save_email(settings: Settings, tenant_id: str, data: dict, smtp_password: str | None) -> None:
    async with async_session() as s:
        row = (await s.execute(select(EmailConfig).where(EmailConfig.tenant_id == tenant_id))).scalar_one_or_none()
        if not row:
            row = EmailConfig(tenant_id=tenant_id)
            s.add(row)
        row.method = data.get("method", "rca")
        row.smtp_host = data.get("smtp_host", "").strip()
        row.smtp_port = data.get("smtp_port", "").strip()
        row.from_address = data.get("from_address", "").strip()
        row.smtp_user = data.get("smtp_user", "").strip()
        row.recipients = data.get("recipients", "").strip()
        if smtp_password and smtp_password != SENTINEL:
            row.pass_enc = crypto.encrypt(smtp_password, _mk(settings))
        await s.commit()


# ---- Watch list ----

async def list_watched(tenant_id: str) -> set[str]:
    async with async_session() as s:
        rows = (await s.execute(select(WatchedFlow.iflow_id).where(WatchedFlow.tenant_id == tenant_id))).scalars().all()
        return set(rows)


async def watch(tenant_id: str, iflow_id: str, name: str = "") -> None:
    async with async_session() as s:
        exists = (await s.execute(select(WatchedFlow).where(
            WatchedFlow.tenant_id == tenant_id, WatchedFlow.iflow_id == iflow_id))).scalar_one_or_none()
        if not exists:
            s.add(WatchedFlow(tenant_id=tenant_id, iflow_id=iflow_id, name=name))
            await s.commit()


async def unwatch(tenant_id: str, iflow_id: str) -> None:
    async with async_session() as s:
        await s.execute(delete(WatchedFlow).where(
            WatchedFlow.tenant_id == tenant_id, WatchedFlow.iflow_id == iflow_id))
        await s.commit()


# ---- Integration sources (APIM / AEM) ----

async def get_source(tenant_id: str, kind: str) -> IntegrationSource | None:
    async with async_session() as s:
        return (await s.execute(select(IntegrationSource).where(
            IntegrationSource.tenant_id == tenant_id, IntegrationSource.kind == kind))).scalar_one_or_none()


async def save_source(settings: Settings, tenant_id: str, kind: str, data: dict, secret: str | None) -> None:
    async with async_session() as s:
        row = (await s.execute(select(IntegrationSource).where(
            IntegrationSource.tenant_id == tenant_id, IntegrationSource.kind == kind))).scalar_one_or_none()
        if not row:
            row = IntegrationSource(tenant_id=tenant_id, kind=kind)
            s.add(row)
        row.enabled = bool(data.get("enabled", False))
        row.auth_type = data.get("auth_type", "oauth")
        row.base_url = data.get("base_url", "").strip()
        row.token_url = data.get("token_url", "").strip()
        row.client_id = data.get("client_id", "").strip()
        row.username = data.get("username", "").strip()
        row.extra = data.get("extra", {}) or {}
        if secret and secret != SENTINEL:
            row.secret_enc = crypto.encrypt(secret, _mk(settings))
        await s.commit()


async def get_source_secret(settings: Settings, tenant_id: str, kind: str) -> str | None:
    row = await get_source(tenant_id, kind)
    return crypto.decrypt(row.secret_enc, _mk(settings)) if row and row.secret_enc else None


# ---- Agent runs ----

async def save_run(tenant_id: str, run: dict) -> None:
    async with async_session() as s:
        existing = (await s.execute(select(AgentRun).where(
            AgentRun.tenant_id == tenant_id, AgentRun.run_id == run["run_id"]))).scalar_one_or_none()
        if not existing:
            existing = AgentRun(tenant_id=tenant_id, run_id=run["run_id"])
            s.add(existing)
        for k in ("status", "state", "request", "classification", "citations",
                  "brief", "artifact", "validation", "score", "steps", "attempts"):
            setattr(existing, k, run.get(k))
        await s.commit()


async def get_run(tenant_id: str, run_id: str) -> AgentRun | None:
    async with async_session() as s:
        return (await s.execute(select(AgentRun).where(
            AgentRun.tenant_id == tenant_id, AgentRun.run_id == run_id))).scalar_one_or_none()
