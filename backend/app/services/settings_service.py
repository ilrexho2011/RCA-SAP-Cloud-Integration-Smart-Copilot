"""Settings service — CPI connection, AI engine, email (tenant-scoped, DB-backed)."""
from __future__ import annotations

from ..config import Settings
from ..connectors.aem import AemConnector
from ..connectors.apim import ApimConnector
from ..db import repos
from ..llm.provider import get_provider
from ..models.schemas import (
    AiEngineInfo,
    AiEngineTestResult,
    AiEngineUpdate,
    ConnectionInfo,
    ConnectionUpdate,
    EmailAlertsInfo,
    EmailAlertsUpdate,
    EmailTestResult,
    SourceInfo,
    SourceTestResult,
    SourceUpdate,
)
from .connection import effective_mode


# ---- CPI connection ----

async def get_connection(settings: Settings, tenant_id: str) -> ConnectionInfo:
    row = await repos.get_connection(tenant_id)
    secret_set = bool(row and row.secret_enc)
    configured = bool(row and row.base_url and row.client_id and secret_set)
    return ConnectionInfo(
        configured=configured,
        mode=await effective_mode(settings, tenant_id),
        base_url=(row.base_url if row else "") or settings.cpi_base_url,
        token_url=(row.token_url if row else "") or settings.cpi_token_url,
        client_id=(row.client_id if row else "") or settings.cpi_client_id,
        web_ide_url=row.web_ide_url if row else "",
        secret_set=secret_set or bool(settings.cpi_client_secret),
        rt_base_url=row.rt_base_url if row else "",
        rt_token_url=row.rt_token_url if row else "",
        rt_client_id=row.rt_client_id if row else "",
        rt_secret_set=bool(row and row.rt_secret_enc),
    )


async def save_connection(settings: Settings, tenant_id: str, update: ConnectionUpdate) -> ConnectionInfo:
    await repos.save_connection(
        settings, tenant_id,
        data={
            "base_url": update.base_url, "token_url": update.token_url, "client_id": update.client_id,
            "web_ide_url": update.web_ide_url, "mode": update.mode or "live",
            "rt_base_url": update.rt_base_url, "rt_token_url": update.rt_token_url,
            "rt_client_id": update.rt_client_id,
        },
        secret=update.client_secret, rt_secret=update.rt_client_secret,
    )
    return await get_connection(settings, tenant_id)


async def switch_mode(settings: Settings, tenant_id: str, mode: str) -> ConnectionInfo:
    await repos.set_connection_mode(tenant_id, mode if mode in ("live", "demo") else "demo")
    return await get_connection(settings, tenant_id)


# ---- AI engine ----

async def get_ai_engine(tenant_id: str) -> AiEngineInfo:
    row = await repos.get_ai(tenant_id)
    key_set = bool(row and row.key_enc)
    return AiEngineInfo(
        provider=row.provider if row else "stub",
        endpoint=row.endpoint if row else "",
        model=row.model if row else "",
        key_set=key_set,
        active=await repos.has_ai_engine(tenant_id),
    )


async def save_ai_engine(settings: Settings, tenant_id: str, update: AiEngineUpdate) -> AiEngineInfo:
    await repos.save_ai(settings, tenant_id,
                        data={"provider": update.provider, "endpoint": update.endpoint, "model": update.model},
                        api_key=update.api_key)
    return await get_ai_engine(tenant_id)


async def test_ai_engine(settings: Settings, tenant_id: str) -> AiEngineTestResult:
    provider = await get_provider(settings, tenant_id)
    try:
        out = await provider.complete(system="Reply with the single word: ok.", user="ping", json_mode=False)
        return AiEngineTestResult(ok=True, provider=provider.name,
                                  detail=f"Reachable — sample reply: {out[:60]!r}")
    except Exception as e:  # noqa: BLE001
        return AiEngineTestResult(ok=False, provider=provider.name, detail=f"{type(e).__name__}: {e}")


_DEFAULT_BASE = {
    "openai": "https://api.openai.com/v1", "deepseek": "https://api.deepseek.com",
    "perplexity": "https://api.perplexity.ai", "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
}


async def list_models(settings: Settings, tenant_id: str) -> dict:
    import httpx

    row = await repos.get_ai(tenant_id)
    provider = row.provider if row else "stub"
    if provider == "stub" or not (row and row.key_enc):
        return {"provider": provider, "models": [], "detail": "Configure a provider and API key first."}
    key = await repos.get_ai_key(settings, tenant_id) or ""
    base = (row.endpoint or _DEFAULT_BASE.get(provider, "")).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if provider in ("openai", "deepseek", "perplexity"):
                r = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
                r.raise_for_status()
                ids = [m.get("id", "") for m in r.json().get("data", [])]
            elif provider == "anthropic":
                r = await client.get(f"{base}/v1/models",
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
                r.raise_for_status()
                ids = [m.get("id", "") for m in r.json().get("data", [])]
            elif provider == "gemini":
                r = await client.get(f"{base}/v1beta/models", params={"key": key})
                r.raise_for_status()
                ids = [m.get("name", "").split("/")[-1] for m in r.json().get("models", [])]
            else:
                return {"provider": provider, "models": [],
                        "detail": "Model listing not available for this provider — enter the deployment name."}
        ids = sorted(i for i in ids if i)
        return {"provider": provider, "models": ids, "detail": f"{len(ids)} model(s) available."}
    except Exception as e:  # noqa: BLE001
        detail = e.response.text[:200] if hasattr(e, "response") and e.response is not None else str(e)
        return {"provider": provider, "models": [], "detail": f"Could not list models: {detail}"}


# ---- Email alerts ----

async def get_email(tenant_id: str) -> EmailAlertsInfo:
    row = await repos.get_email(tenant_id)
    method = row.method if row else "rca"
    configured = method == "rca" or bool(row and row.smtp_host and row.from_address)
    return EmailAlertsInfo(
        configured=configured, method=method,
        smtp_host=row.smtp_host if row else "", smtp_port=row.smtp_port if row else "",
        from_address=row.from_address if row else "", smtp_user=row.smtp_user if row else "",
        recipients=row.recipients if row else "", password_set=bool(row and row.pass_enc),
    )


async def save_email(settings: Settings, tenant_id: str, update: EmailAlertsUpdate) -> EmailAlertsInfo:
    await repos.save_email(settings, tenant_id,
                           data={"method": update.method, "smtp_host": update.smtp_host,
                                 "smtp_port": update.smtp_port, "from_address": update.from_address,
                                 "smtp_user": update.smtp_user, "recipients": update.recipients},
                           smtp_password=update.smtp_password)
    return await get_email(tenant_id)


# ---- APIM / AEM sources ----

async def get_source(tenant_id: str, kind: str) -> SourceInfo:
    row = await repos.get_source(tenant_id, kind)
    return SourceInfo(
        kind=kind,
        enabled=bool(row and row.enabled),
        auth_type=row.auth_type if row else ("oauth" if kind == "APIM" else "basic"),
        base_url=row.base_url if row else "",
        token_url=row.token_url if row else "",
        client_id=row.client_id if row else "",
        username=row.username if row else "",
        vpn=(row.extra or {}).get("vpn", "") if row else "",
        analytics_base_url=(row.extra or {}).get("analytics_base_url", "") if row else "",
        secret_set=bool(row and row.secret_enc),
    )


async def save_source(settings: Settings, tenant_id: str, kind: str, update: SourceUpdate) -> SourceInfo:
    await repos.save_source(settings, tenant_id, kind,
                            data={"enabled": update.enabled, "auth_type": update.auth_type,
                                  "base_url": update.base_url, "token_url": update.token_url,
                                  "client_id": update.client_id, "username": update.username,
                                  "extra": {"vpn": update.vpn,
                                            "analytics_base_url": update.analytics_base_url}},
                            secret=update.secret)
    return await get_source(tenant_id, kind)


async def test_source(settings: Settings, tenant_id: str, kind: str) -> SourceTestResult:
    row = await repos.get_source(tenant_id, kind)
    if not row or not row.base_url:
        return SourceTestResult(ok=False, kind=kind, detail="Not configured — enter the base URL and credentials.")
    secret = await repos.get_source_secret(settings, tenant_id, kind) or ""
    try:
        if kind == "APIM":
            conn = ApimConnector(row.base_url, row.token_url, row.client_id, secret,
                                 analytics_base_url=(row.extra or {}).get("analytics_base_url", ""))
        else:
            conn = AemConnector(row.base_url, (row.extra or {}).get("vpn", ""), auth_type=row.auth_type,
                                username=row.username, secret=secret, token_url=row.token_url, client_id=row.client_id)
        data = await conn.connected_system()
        headline = data["metrics"][0]
        return SourceTestResult(ok=True, kind=kind,
                                detail=f"Connected — {headline['label']}: {headline['value']}.")
    except Exception as e:  # noqa: BLE001
        return SourceTestResult(ok=False, kind=kind, detail=str(e))


async def test_email(tenant_id: str) -> EmailTestResult:
    row = await repos.get_email(tenant_id)
    if not row or not row.recipients:
        return EmailTestResult(ok=False, detail="No recipients configured.")
    if row.method == "rca":
        return EmailTestResult(ok=True, detail=f"RCA mail service ready — a test alert would be delivered to {row.recipients}.")
    missing = [k for k in ("smtp_host", "smtp_port", "from_address") if not getattr(row, k)]
    if missing:
        return EmailTestResult(ok=False, detail=f"SMTP config incomplete: missing {', '.join(missing)}.")
    return EmailTestResult(ok=True, detail=f"SMTP config valid ({row.smtp_host}:{row.smtp_port}). Delivery is performed by the deployed backend host.")
