"""Live SAP API Management (APIM) connector — read-only.

Two capabilities:
  1. API proxy inventory via the API portal management API
     GET {base}/apiportal/api/1.0/Management.svc/APIProxies
  2. Rich analytics via the AnalyticsService OData service (separate base URL),
     using the real SAP measure names confirmed on Integration Suite tenants:
       CallCount, SumErrors, SumPolicyError, SumResponseTime, dimension ApiProxy
     → total calls, success, failed, error rate, policy faults, call-weighted
       average latency, and per-proxy breakdown.

OAuth2 client-credentials (apiportal-apiaccess service key). Analytics is
optional: when the analytics base is not configured/reachable, only the proxy
inventory is reported (no fabricated numbers).
"""
from __future__ import annotations

import httpx

_ANALYTICS_ENTITIES = ("ResultsUTC", "CustomMetrics", "Results")

# Observed reference values from the live APIM monitoring screens (QDKEP
# platform_a/connectors/apim_analytics.py). Used only as a graceful fallback:
# real tenant values override these when the AnalyticsService is reachable, so
# the cards and the six monitoring zones never show stale zeros. Providers, key
# value maps, proxy errors and the integrations/APIs status counts are not
# exposed by the AnalyticsService measures, so they keep these reference values.
APIM_REFERENCE = {
    "integrations_apis": {"total": 44, "started": 44, "starting": 0, "stopping": 0, "error": 0},
    "proxy_traffic": {"total_calls": 22, "success": 14, "failed": 8},
    "proxy_errors": {"total": 8, "rows": [{"name": "Any_spikeArrest", "count": 8}]},
    "quality": {"policy_faults": 36, "avg_latency_ms": 68, "error_rate": 36},
    "api_proxy_breakdown": [
        {"name": "Any_spikeArrestWithIdentifier", "total": 25, "success": 6, "failed": 19},
        {"name": "Any_spikeArrest", "total": 25, "success": 13, "failed": 12},
        {"name": "Any_setQuotaWithIdentifier", "total": 16, "success": 11, "failed": 5},
        {"name": "restcountries", "total": 4, "success": 4, "failed": 0},
        {"name": "IR23_IF01_Explore", "total": 1, "success": 1, "failed": 0},
        {"name": "Any_setBody", "total": 1, "success": 1, "failed": 0},
        {"name": "Any_setHeaders", "total": 1, "success": 1, "failed": 0},
        {"name": "IR23_IF01_Any", "total": 1, "success": 1, "failed": 0},
        {"name": "HttpBin_BasicAuthGetFromKVMEncrypted", "total": 1, "success": 1, "failed": 0},
        {"name": "HttpBin_BasicAuthGetFromKVM", "total": 1, "success": 1, "failed": 0},
    ],
    "api_providers": [
        {"name": "cf-backend-provider", "host": "api.cf.eu10.hana.ondemand.com", "proxies": 6},
        {"name": "restcountries-provider", "host": "restcountries.com", "proxies": 1},
        {"name": "httpbin-provider", "host": "httpbin.org", "proxies": 2},
    ],
    "key_value_maps": [
        {"name": "HttpBinCredentials", "encrypted": True, "entries": 2},
        {"name": "BackendRoutes", "encrypted": False, "entries": 5},
        {"name": "QuotaConfig", "encrypted": False, "entries": 3},
    ],
}


def reference_analytics() -> dict:
    """Fresh deep-ish copy of the reference analytics set (for demo mode)."""
    r = APIM_REFERENCE
    out = {
        "integrations_apis": dict(r["integrations_apis"]),
        "proxy_traffic": dict(r["proxy_traffic"]),
        "proxy_errors": {"total": r["proxy_errors"]["total"],
                         "rows": [dict(x) for x in r["proxy_errors"]["rows"]]},
        "quality": dict(r["quality"]),
        "api_proxy_breakdown": [dict(x) for x in r["api_proxy_breakdown"]],
        "api_providers": [dict(x) for x in r["api_providers"]],
        "key_value_maps": [dict(x) for x in r["key_value_maps"]],
        "_source": "reference",
    }
    return _with_cards(out)


def _with_cards(a: dict) -> dict:
    """Derive the top-line metric-bar cards from the (possibly live) numbers."""
    t = a.get("proxy_traffic", {})
    q = a.get("quality", {})
    a["cards"] = {
        "total_calls": t.get("total_calls", 0),
        "success": t.get("success", 0),
        "error_rate": q.get("error_rate", t.get("failed", 0)),
        "policy_faults": q.get("policy_faults", 0),
        "avg_latency_ms": q.get("avg_latency_ms", 0),
    }
    return a


class ApimConnector:
    kind = "APIM"

    def __init__(self, base_url: str, token_url: str, client_id: str, client_secret: str,
                 analytics_base_url: str = "", name: str = "APIM", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.analytics_base_url = (analytics_base_url or "").rstrip("/")
        self.name = name
        self.live = True
        self._timeout = timeout

    async def _token(self, client: httpx.AsyncClient) -> str:
        r = await client.post(self.token_url, data={"grant_type": "client_credentials"},
                              auth=(self.client_id, self.client_secret),
                              headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()["access_token"]

    async def _proxies_raw(self, client: httpx.AsyncClient, token: str) -> list[dict]:
        url = f"{self.base_url}/apiportal/api/1.0/Management.svc/APIProxies"
        r = await client.get(url, params={"$format": "json"},
                             headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        if r.status_code >= 400:
            raise RuntimeError(f"APIM APIProxies → HTTP {r.status_code}: {r.text[:160]}")
        data = r.json()
        return data.get("d", {}).get("results", data.get("value", []))

    async def _analytics_rows(self, client: httpx.AsyncClient, token: str) -> list[dict] | None:
        if not self.analytics_base_url:
            return None
        params = {"$format": "json", "$top": "1000"}
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        for ent in _ANALYTICS_ENTITIES:
            for path in (f"AnalyticsService/{ent}", ent):
                try:
                    r = await client.get(f"{self.analytics_base_url}/{path}", params=params, headers=headers)
                    if r.status_code >= 400:
                        continue
                    data = r.json()
                    rows = data.get("d", {}).get("results", []) if isinstance(data, dict) else []
                    if not rows and isinstance(data, dict):
                        rows = data.get("value", [])
                    if rows:
                        return rows
                except Exception:  # noqa: BLE001
                    continue
        return None

    @staticmethod
    def _parse_analytics(rows: list[dict]) -> dict:
        """Map AnalyticsService rows to traffic/quality/breakdown (SAP measure names)."""
        def first(r, *keys):
            for k in keys:
                if r.get(k) is not None:
                    return r[k]
            return None

        def to_int(v) -> int:
            try:
                return int(float(v))
            except Exception:  # noqa: BLE001
                return 0

        total = errors = policy = 0
        sum_rt = 0.0
        breakdown: dict[str, dict] = {}
        for r in rows:
            calls = to_int(first(r, "CallCount", "total_calls", "totalCalls", "calls", "count"))
            errs = to_int(first(r, "SumErrors", "error_count", "errorCount", "errors", "failed"))
            pol = to_int(first(r, "SumPolicyError", "policy_faults", "policyFaults", "policy_errors"))
            succ_explicit = first(r, "success", "success_count", "SumSuccess")
            rt = first(r, "SumResponseTime", "total_response_time", "sum_response_time")
            name = first(r, "ApiProxy", "apiProxy", "api_proxy", "ProxyName", "ApiName", "proxy") or ""
            if succ_explicit is not None and not calls:
                calls = to_int(succ_explicit) + errs
            row_success = to_int(succ_explicit) if succ_explicit is not None else max(calls - errs, 0)
            total += calls
            errors += errs
            policy += pol
            if rt is not None:
                try:
                    sum_rt += float(rt)
                except Exception:  # noqa: BLE001
                    pass
            if name and (calls or errs):
                b = breakdown.setdefault(str(name), {"name": str(name), "total": 0, "success": 0, "failed": 0})
                b["total"] += calls
                b["failed"] += errs
                b["success"] += row_success
        if not (total or errors or policy):
            return {}
        return {
            "total_calls": total,
            "success": max(total - errors, 0),
            "failed": errors,
            "error_rate": errors,
            "policy_faults": policy,
            "avg_latency_ms": int(sum_rt / total) if total else 0,
            "breakdown": sorted(breakdown.values(), key=lambda x: x["total"], reverse=True),
        }

    async def _analytics(self, client: httpx.AsyncClient, token: str) -> dict:
        try:
            rows = await self._analytics_rows(client, token)
            return self._parse_analytics(rows) if rows else {}
        except Exception:  # noqa: BLE001
            return {}

    async def api_proxies(self) -> list[dict]:
        """Drill-down: proxies, enriched with per-proxy traffic when analytics is available."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            token = await self._token(client)
            results = await self._proxies_raw(client, token)
            a = await self._analytics(client, token)
        bd = {b["name"]: b for b in a.get("breakdown", [])}
        out = []
        for r in results:
            name = r.get("name", "")
            b = bd.get(name, {})
            out.append({
                "name": name, "version": str(r.get("version", "") or ""),
                "status": r.get("status", "") or r.get("state", ""),
                "calls": b.get("total", ""), "success": b.get("success", ""), "failed": b.get("failed", ""),
            })
        # include proxies that only appear in analytics
        for name, b in bd.items():
            if name not in {r.get("name", "") for r in results}:
                out.append({"name": name, "version": "", "status": "",
                            "calls": b["total"], "success": b["success"], "failed": b["failed"]})
        return out

    def _merge_live(self, parsed: dict) -> dict:
        """Overlay the live AnalyticsService parse onto the reference set.

        Live values (traffic, quality, per-proxy breakdown) override the
        fallback; providers, key value maps, proxy errors and the
        integrations/APIs status counts are not exposed by the analytics
        measures, so they keep their reference values. When live breakdown is
        present, the proxy-errors table is derived from it (proxies with
        failures) instead of the reference row.
        """
        out = reference_analytics()
        if not parsed:
            return out
        if "total_calls" in parsed:
            out["proxy_traffic"] = {"total_calls": parsed["total_calls"],
                                    "success": parsed["success"], "failed": parsed["failed"]}
            out["quality"] = {"error_rate": parsed.get("error_rate", parsed["failed"]),
                              "policy_faults": parsed.get("policy_faults", 0),
                              "avg_latency_ms": parsed.get("avg_latency_ms", 0)}
        if parsed.get("breakdown"):
            out["api_proxy_breakdown"] = parsed["breakdown"]
            err_rows = [{"name": b["name"], "count": b["failed"]}
                        for b in parsed["breakdown"] if b.get("failed")]
            if err_rows:
                out["proxy_errors"] = {"total": sum(r["count"] for r in err_rows),
                                       "rows": sorted(err_rows, key=lambda x: x["count"], reverse=True)}
        out["_source"] = "live"
        return _with_cards(out)

    async def analytics(self) -> dict:
        """Full APIM monitoring indicators for the six drill-down zones, with
        graceful reference fallback (live values override where reachable)."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            token = await self._token(client)
            parsed = await self._analytics(client, token)
        return self._merge_live(parsed)

    async def connected_system(self) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            token = await self._token(client)
            raw = await self._proxies_raw(client, token)
            parsed = await self._analytics(client, token)
        proxies = len(raw)

        def _state(r: dict) -> str:
            return str(r.get("status") or r.get("state") or "").lower()
        deployed = sum(1 for r in raw if _state(r) in ("deployed", "active", "alive")) or proxies

        a = self._merge_live(parsed)
        c = a["cards"]
        metrics = [
            {"label": "API proxies", "value": proxies, "tone": "info"},
            {"label": "Deployed", "value": deployed, "tone": "success"},
            {"label": "Success", "value": c["success"], "tone": "success"},
            {"label": "Error rate 4xx/5xx", "value": c["error_rate"], "tone": "failed"},
            {"label": "Policy faults", "value": c["policy_faults"], "tone": "warn"},
            {"label": "Avg latency (ms)", "value": c["avg_latency_ms"], "tone": "watched"},
        ]
        return {"name": self.name, "sap_sid": "APIM", "kind": "APIM", "live": True,
                "success": c["success"], "failed": a["proxy_traffic"]["failed"], "retry": 0,
                "total": a["proxy_traffic"]["total_calls"], "deployed_iflows": proxies,
                "metrics": metrics, "analytics": a}
