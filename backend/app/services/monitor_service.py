"""Monitor service — watch list, 'Ask your monitoring', JMS queues (tenant-scoped)."""
from __future__ import annotations

from ..config import Settings
from ..connectors.aem import AemConnector
from ..connectors.apim import ApimConnector
import inspect

from ..db import repos
from .connection import resolve_connector
from . import monitoring_service


async def list_flows(settings: Settings, tenant_id: str) -> list[dict]:
    conn = await resolve_connector(settings, tenant_id)
    arts = await conn.runtime_artifacts() if hasattr(conn, "runtime_artifacts") else []
    watched = await repos.list_watched(tenant_id)
    return [
        {"id": a.get("id", ""), "name": a.get("name", ""), "status": a.get("status", ""),
         "watched": a.get("id", "") in watched}
        for a in arts
    ]


async def watch(tenant_id: str, iflow_id: str) -> dict:
    await repos.watch(tenant_id, iflow_id)
    return {"id": iflow_id, "watched": True, "watch_count": len(await repos.list_watched(tenant_id))}


async def unwatch(tenant_id: str, iflow_id: str) -> dict:
    await repos.unwatch(tenant_id, iflow_id)
    return {"id": iflow_id, "watched": False, "watch_count": len(await repos.list_watched(tenant_id))}


async def system_detail(settings: Settings, tenant_id: str, kind: str) -> dict:
    """Drill-down items for a connected system (CPI iFlows / APIM proxies / AEM queues)."""
    if kind == "CPI":
        conn = await resolve_connector(settings, tenant_id)
        arts = await conn.runtime_artifacts() if hasattr(conn, "runtime_artifacts") else []
        items = [{"name": a.get("name") or a.get("id", ""), "status": a.get("status", ""), "id": a.get("id", "")}
                 for a in arts]
        return {"kind": "CPI", "columns": ["iFlow", "Status"], "items": items, "error": None}

    row = await repos.get_source(tenant_id, kind)
    if not row or not row.base_url:
        # No live source configured. In demo mode, serve the bundled APIM
        # analytics + proxy list so the six zones still render.
        if kind == "APIM":
            base = await resolve_connector(settings, tenant_id)
            apim_analytics = getattr(base, "apim_analytics", None)
            apim_proxies = getattr(base, "apim_proxies", None)
            if callable(apim_analytics):
                if callable(apim_proxies):
                    items = apim_proxies()
                    items = await items if inspect.isawaitable(items) else items
                else:
                    items = []
                analytics = apim_analytics()
                analytics = await analytics if inspect.isawaitable(analytics) else analytics
                return {"kind": "APIM", "columns": ["API proxy", "Calls", "Success", "Failed"],
                        "items": items, "error": None, "analytics": analytics}
        return {"kind": kind, "columns": [], "items": [], "error": "Not configured."}
    secret = await repos.get_source_secret(settings, tenant_id, kind) or ""
    try:
        if kind == "APIM":
            conn = ApimConnector(row.base_url, row.token_url, row.client_id, secret,
                                 analytics_base_url=(row.extra or {}).get("analytics_base_url", ""))
            items = await conn.api_proxies()
            analytics = await conn.analytics()
            has_traffic = any(it.get("calls") not in ("", None) for it in items)
            cols = ["API proxy", "Calls", "Success", "Failed"] if has_traffic else ["API proxy", "Version", "Status"]
            return {"kind": kind, "columns": cols, "items": items, "error": None, "analytics": analytics}
        else:
            conn = AemConnector(row.base_url, (row.extra or {}).get("vpn", ""), auth_type=row.auth_type,
                                username=row.username, secret=secret, token_url=row.token_url, client_id=row.client_id)
            items = await conn.queue_list()
            cols = ["Queue", "Spool (MB)", "Access"]
        return {"kind": kind, "columns": cols, "items": items, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"kind": kind, "columns": [], "items": [], "error": str(e)}


async def queues(settings: Settings, tenant_id: str) -> list[dict]:
    conn = await resolve_connector(settings, tenant_id)
    if hasattr(conn, "jms_queues"):
        return await conn.jms_queues()
    return []


async def queues_overview(settings: Settings, tenant_id: str) -> dict:
    """Combined Queues + Data Stores view with indicator cards.

    Live degrades gracefully: whichever source (JMS queues / Data Stores) is
    unavailable simply stays empty — no fabricated rows.
    """
    conn = await resolve_connector(settings, tenant_id)
    error = None
    q: list[dict] = []
    ds: list[dict] = []
    try:
        if hasattr(conn, "jms_queues"):
            q = await conn.jms_queues()
    except Exception as e:  # noqa: BLE001
        error = f"queues: {e}"
    try:
        if hasattr(conn, "data_stores"):
            ds = await conn.data_stores()
    except Exception as e:  # noqa: BLE001
        error = (error + "; " if error else "") + f"data stores: {e}"

    q_depth = sum(int(x.get("depth", 0) or 0) for x in q)
    q_stuck = sum(int(x.get("stuck", 0) or 0) for x in q)
    q_retry = sum(int(x.get("retry", 0) or 0) for x in q)
    ds_entries = sum(int(x.get("entries", 0) or 0) for x in ds)
    ds_overdue = sum(int(x.get("overdue", 0) or 0) for x in ds)

    kpis = [
        {"label": "Queues", "value": len(q), "tone": "info"},
        {"label": "Queued messages", "value": q_depth, "tone": "watched"},
        {"label": "Stuck", "value": q_stuck, "tone": "failed" if q_stuck else "success"},
        {"label": "Retry backlog", "value": q_retry, "tone": "warn" if q_retry else "success"},
        {"label": "Data stores", "value": len(ds), "tone": "info"},
        {"label": "Store entries", "value": ds_entries, "tone": "watched"},
        {"label": "Overdue entries", "value": ds_overdue, "tone": "failed" if ds_overdue else "success"},
    ]
    return {"kpis": kpis, "queues": q, "datastores": ds, "error": error}


async def ask(settings: Settings, tenant_id: str, question: str) -> dict:
    ov = await monitoring_service.get_overview(settings, tenant_id)
    q = question.lower()
    sys = ov.systems[0] if ov.systems else None
    failed = next((k.value for k in ov.kpis if k.key == "failed"), 0)
    completed = next((k.value for k in ov.kpis if k.key == "completed"), 0)
    patterns = next((k.value for k in ov.kpis if k.key == "patterns"), 0)
    deployed = sys.deployed_iflows if sys else 0
    total = sys.total if sys else 0

    def ans(text: str, data: dict | None = None, evaluated: bool = True) -> dict:
        return {"question": question, "answer": text, "data": data or {},
                "evaluated": evaluated, "source": ov.source}

    if "fail" in q and ("regular" in q or "pattern" in q):
        ifaces = sorted({m.interface for m in ov.failed_messages})
        return ans(f"{len(ifaces)} interface(s) are failing: {', '.join(ifaces) or 'none'}.", {"interfaces": ifaces})
    if "fail" in q:
        return ans(f"{failed} message(s) failed in the last 24h across {ov.sources_connected} system(s).",
                   {"failed": failed, "patterns": patterns})
    if "processed" in q or ("messages" in q and "today" in q):
        return ans(f"{total} message(s) processed in the last 24h ({completed} completed, {failed} failed).",
                   {"total": total, "completed": completed, "failed": failed})
    if "deployed" in q:
        return ans(f"{deployed} iFlow(s) are deployed on {sys.name if sys else 'the tenant'}.", {"deployed": deployed})
    if "slow" in q or "runtime" in q:
        return ans("Runtime/latency ranking needs per-message processing times — available once a live "
                   "tenant with MPL timing is connected.", evaluated=False)
    if "haven't run" in q or "not run" in q or "30 day" in q:
        return ans("Idle-flow detection needs run history over time — available once monitoring has been "
                   "collecting from a live tenant.", evaluated=False)
    return ans(f"Current signals: {completed} completed, {failed} failed, {deployed} deployed iFlows in the "
               f"last 24h. Try one of the suggested questions for a precise answer.",
               {"completed": completed, "failed": failed, "deployed": deployed})
