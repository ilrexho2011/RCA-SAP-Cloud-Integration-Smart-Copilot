"""Live SAP Advanced Event Mesh (AEM) connector — read-only.

Uses the SEMP v2 monitor API:
  GET {base}/SEMP/v2/monitor/msgVpns/{vpn}/queues

Auth: basic (username/password) or OAuth bearer.
"""
from __future__ import annotations

import base64

import httpx


class AemConnector:
    kind = "AEM"

    def __init__(self, base_url: str, vpn: str, *, auth_type: str = "basic",
                 username: str = "", secret: str = "", token_url: str = "", client_id: str = "",
                 name: str = "AEM", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.vpn = vpn
        self.auth_type = auth_type
        self.username = username
        self.secret = secret
        self.token_url = token_url
        self.client_id = client_id
        self.name = name
        self.live = True
        self._timeout = timeout

    async def _auth_header(self, client: httpx.AsyncClient) -> dict:
        if self.auth_type == "oauth":
            r = await client.post(self.token_url, data={"grant_type": "client_credentials"},
                                  auth=(self.client_id, self.secret))
            r.raise_for_status()
            return {"Authorization": f"Bearer {r.json()['access_token']}"}
        token = base64.b64encode(f"{self.username}:{self.secret}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    async def _queues_raw(self, client: httpx.AsyncClient) -> list[dict]:
        headers = await self._auth_header(client)
        url = f"{self.base_url}/SEMP/v2/monitor/msgVpns/{self.vpn}/queues"
        # No 'select' — some brokers reject comma-encoded select values; read full objects.
        r = await client.get(url, params={"count": "100"}, headers={**headers, "Accept": "application/json"})
        if r.status_code >= 400:
            raise RuntimeError(f"AEM SEMP queues → HTTP {r.status_code}: {r.text[:160]}")
        return r.json().get("data", [])

    async def queue_list(self) -> list[dict]:
        """Drill-down list of queues."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            data = await self._queues_raw(client)
        return [
            {"name": q.get("queueName", ""),
             "spool_mb": int(q.get("msgSpoolUsage", 0) or 0) // 1_000_000,
             "access": q.get("accessType", ""),
             "status": "durable" if q.get("durable") else "non-durable"}
            for q in data
        ]

    async def connected_system(self) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            data = await self._queues_raw(client)
        queues = len(data)
        spool_bytes = sum(int(q.get("msgSpoolUsage", 0) or 0) for q in data)
        max_bytes = sum(int(q.get("maxMsgSpoolUsage", 0) or 0) for q in data) * 1_000_000
        spool_mb = spool_bytes // 1_000_000
        durable = sum(1 for q in data if q.get("durable"))
        consumers = sum(int(q.get("bindCount", 0) or 0) for q in data)
        # queues holding a backlog (spool in use) — real signal, no fabrication
        backlog = sum(1 for q in data if int(q.get("msgSpoolUsage", 0) or 0) > 0)
        ingress_down = sum(1 for q in data if q.get("ingressEnabled") is False)
        return {
            "name": self.name, "sap_sid": "AEM", "kind": "AEM", "live": True,
            "success": 0, "failed": backlog, "retry": 0, "total": spool_mb, "deployed_iflows": queues,
            "metrics": [
                {"label": "Queues", "value": queues, "tone": "info"},
                {"label": "Durable", "value": durable, "tone": "info"},
                {"label": "Spool usage (MB)", "value": spool_mb, "tone": "warn"},
                {"label": "With backlog", "value": backlog, "tone": "failed" if backlog else "success"},
                {"label": "Bound consumers", "value": consumers, "tone": "watched"},
                {"label": "Ingress off", "value": ingress_down, "tone": "warn"},
            ],
        }
