"""Aggregate connector reads into the monitoring overview contract."""
from __future__ import annotations

from ..config import Settings
from ..connectors.aem import AemConnector
from ..connectors.apim import ApimConnector
from ..db import repos
from ..models.schemas import (
    ConnectedSystem,
    ConnectionTestResult,
    FailedMessage,
    KpiCard,
    MonitoringOverview,
)
from .connection import resolve_connector

_ERROR_STATUSES = {"FAILED", "ERROR", "DEAD"}


def _stub_system(kind: str, name: str, note: str) -> ConnectedSystem:
    return ConnectedSystem(name=name, sap_sid=kind, kind=kind, live=False,
                           success=0, failed=0, retry=0, total=0, deployed_iflows=0,
                           metrics=[], note=note)


async def _live_source_system(settings: Settings, tenant_id: str, kind: str):
    """Return (ConnectedSystem | None, error | None). A configured source is
    always shown — with a state note when it is disabled or erroring — so it
    never silently disappears."""
    row = await repos.get_source(tenant_id, kind)
    if not row or not row.base_url:            # truly unconfigured → absent
        return None, None
    disp = f"{kind}-RCA ({row.base_url.split('//')[-1][:24]})"
    if not row.enabled:
        return _stub_system(kind, disp, "Configured but disabled — enable it in Settings to include live data."), None
    secret = await repos.get_source_secret(settings, tenant_id, kind) or ""
    try:
        if kind == "APIM":
            conn = ApimConnector(row.base_url, row.token_url, row.client_id, secret,
                                 analytics_base_url=(row.extra or {}).get("analytics_base_url", ""),
                                 name=f"APIM-RCA ({row.base_url.split('//')[-1][:24]})")
        else:
            conn = AemConnector(row.base_url, (row.extra or {}).get("vpn", ""),
                                auth_type=row.auth_type, username=row.username, secret=secret,
                                token_url=row.token_url, client_id=row.client_id, name="AEM-RCA (Event Mesh)")
        return ConnectedSystem(**await conn.connected_system()), None
    except Exception as e:  # noqa: BLE001
        return _stub_system(kind, disp, f"Unreachable: {e}"), f"{kind}: {e}"


def _cpi_system_from_mpls(conn, mpls: list, artifacts: list) -> ConnectedSystem:
    success = sum(1 for m in mpls if m.get("status") == "COMPLETED")
    failed = sum(1 for m in mpls if m.get("status") in _ERROR_STATUSES)
    retry = sum(1 for m in mpls if m.get("status") == "RETRY")
    total = len(mpls)
    deployed = len(artifacts)
    return ConnectedSystem(
        name=conn.name, sap_sid=conn.sap_sid, kind=conn.kind, live=conn.live,
        success=success, failed=failed, retry=retry, total=total, deployed_iflows=deployed,
        metrics=[
            {"label": "Success mes.", "value": success, "tone": "success"},
            {"label": "Failed mes.", "value": failed, "tone": "failed"},
            {"label": "Retry mes.", "value": retry, "tone": "watched"},
            {"label": "Total mes.", "value": total, "tone": "info"},
            {"label": "Deployed iFlows", "value": deployed, "tone": "info"},
        ],
    )


def _zero_kpis() -> list[KpiCard]:
    return [
        KpiCard(key="failed", label="Failed messages (24h)", value=0, tone="failed", note="—"),
        KpiCard(key="completed", label="Completed (24h)", value=0, tone="success", note="—"),
        KpiCard(key="watched", label="Systems watched", value=0, tone="watched", note="—"),
        KpiCard(key="patterns", label="Error patterns", value=0, tone="warn", note="—"),
    ]


async def get_overview(settings: Settings, tenant_id: str) -> MonitoringOverview:
    conn = await resolve_connector(settings, tenant_id)

    # Live calls can fail (scope, auth, network) — degrade gracefully with a clear message.
    try:
        mpls = await conn.message_processing_logs(hours=24)
        if hasattr(conn, "connected_systems"):
            systems = [ConnectedSystem(**s) for s in await conn.connected_systems()]
        else:
            artifacts = await conn.runtime_artifacts()
            systems = [_cpi_system_from_mpls(conn, mpls, artifacts)]
    except Exception as e:  # noqa: BLE001
        return MonitoringOverview(
            source="live" if getattr(conn, "live", False) else "demo",
            sources_connected=0, kpis=_zero_kpis(), systems=[], failed_messages=[],
            error=str(e),
        )

    # Live path: append configured APIM/AEM sources (demo already includes all three).
    source_errors: list[str] = []
    if not hasattr(conn, "connected_systems"):
        for kind in ("APIM", "AEM"):
            sysrow, err = await _live_source_system(settings, tenant_id, kind)
            if sysrow:
                systems.append(sysrow)
            if err:
                source_errors.append(err)

    total_failed = sum(s.failed for s in systems)
    total_success = sum(s.success for s in systems)
    connected_count = sum(1 for s in systems if s.live and not s.note)
    watched_note = " · ".join(f"{s.kind} {'✓' if (s.live and not s.note) else '⚠'}" for s in systems)
    patterns = {m.get("integration_flow", "") for m in mpls if m.get("status") in _ERROR_STATUSES}

    kpis = [
        KpiCard(key="failed", label="Failed messages (24h)", value=total_failed, tone="failed",
                note="first-seen captured to monthly store"),
        KpiCard(key="completed", label="Completed (24h)", value=total_success, tone="success",
                note=f"across {len(systems)} connected system(s)"),
        KpiCard(key="watched", label="Systems watched", value=len(systems), tone="watched",
                note=watched_note),
        KpiCard(key="patterns", label="Error patterns", value=len(patterns), tone="warn",
                note="distinct, eligible for KB+RB"),
    ]

    failed_messages = [
        FailedMessage(
            interface=m.get("integration_flow", "—"),
            exception=(m.get("integration_flow", "").split("_")[-1] if m.get("integration_flow") else "—"),
            status="FAILED",
            error=m.get("error") or "",
            timestamp=m.get("log_end"),
        )
        for m in mpls if m.get("status") in _ERROR_STATUSES
    ][:25]

    return MonitoringOverview(
        source="live" if conn.live else "demo",
        sources_connected=connected_count,
        kpis=kpis,
        systems=systems,
        failed_messages=failed_messages,
        error="; ".join(source_errors) if source_errors else None,
    )


async def test_connection(settings: Settings, tenant_id: str) -> ConnectionTestResult:
    conn = await resolve_connector(settings, tenant_id)
    ok, detail = await conn.ping()
    deployed = None
    if ok:
        try:
            deployed = len(await conn.runtime_artifacts())
        except Exception:  # noqa: BLE001
            deployed = None
    return ConnectionTestResult(
        ok=ok, mode="live" if conn.live else "demo", detail=detail, deployed_iflows=deployed,
    )
