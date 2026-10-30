"""Resolve the effective CPI connector for a tenant: stored connection > env > demo."""
from __future__ import annotations

from ..config import Settings
from ..connectors.demo_provider import DemoConnector
from ..connectors.sap_cpi import SapCpiConnector
from ..db import repos


async def effective_mode(settings: Settings, tenant_id: str) -> str:
    if await repos.has_live_connection(tenant_id) or settings.is_live:
        return "live"
    return "demo"


async def resolve_connector(settings: Settings, tenant_id: str):
    # 1) tenant's stored live connection
    if await repos.has_live_connection(tenant_id):
        row = await repos.get_connection(tenant_id)
        return SapCpiConnector(
            base_url=row.base_url, token_url=row.token_url, client_id=row.client_id,
            client_secret=await repos.get_connection_secret(settings, tenant_id) or "",
        )
    # 2) environment-configured connection
    if settings.is_live:
        return SapCpiConnector(
            base_url=settings.cpi_base_url, token_url=settings.cpi_token_url,
            client_id=settings.cpi_client_id, client_secret=settings.cpi_client_secret,
        )
    # 3) demo fallback
    return DemoConnector()
