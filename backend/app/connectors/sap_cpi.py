"""Live SAP CPI / Integration Suite connector (read-only).

Talks to the public OData v2 API of the Integration Suite tenant:
  - MessageProcessingLogs      (runtime message logs / MPL)
  - IntegrationRuntimeArtifacts (deployed iFlows and their status)

Auth is OAuth2 client-credentials against the service key's token URL.
Token is cached until shortly before expiry. Read-only: no writes here.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import httpx

from .base import MplRecord, RuntimeArtifact

_ERROR_STATUSES = {"FAILED", "ERROR", "DEAD"}


class SapCpiConnector:
    kind = "CPI"

    def __init__(
        self,
        base_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        name: str = "CPI tenant",
        sap_sid: str = "CPI",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.name = name
        self.sap_sid = sap_sid
        self.live = True
        self._timeout = timeout
        self._token: str | None = None
        self._token_exp: float = 0.0

    # ---- auth ----
    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        resp = await client.post(
            self.token_url,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_exp = time.time() + int(payload.get("expires_in", 3600))
        return self._token

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
        token = await self._access_token(client)
        resp = await client.get(
            f"{self.base_url}/api/v1/{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        if resp.status_code >= 400:
            hint = ""
            if resp.status_code in (401, 403):
                hint = (" — check the service key OAuth scopes "
                        "(design-time read + MonitoringDataRead for MPL).")
            raise RuntimeError(f"CPI {path} → HTTP {resp.status_code}: {resp.text[:200]}{hint}")
        return resp.json()

    # ---- reads ----
    async def ping(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                data = await self._get(client, "IntegrationRuntimeArtifacts", {"$top": "1", "$format": "json"})
            n = len(data.get("d", {}).get("results", []))
            return True, f"Connected to {self.name}; runtime API reachable (sample={n})."
        except httpx.HTTPStatusError as e:
            return False, f"HTTP {e.response.status_code} from CPI: {e.response.text[:160]}"
        except Exception as e:  # noqa: BLE001
            return False, f"Connection failed: {e}"

    async def message_processing_logs(self, hours: int = 24) -> list[MplRecord]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        # OData v2 datetime literal
        flt = f"LogEnd ge datetime'{since.strftime('%Y-%m-%dT%H:%M:%S')}'"
        params = {
            "$filter": flt,
            "$select": "MessageGuid,Status,IntegrationFlowName,LogEnd",
            "$orderby": "LogEnd desc",
            "$top": "1000",
            "$format": "json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            data = await self._get(client, "MessageProcessingLogs", params)
            out: list[MplRecord] = []
            for r in data.get("d", {}).get("results", []):
                out.append(
                    {
                        "message_guid": r.get("MessageGuid", ""),
                        "status": (r.get("Status") or "").upper(),
                        "integration_flow": r.get("IntegrationFlowName", ""),
                        "log_end": r.get("LogEnd"),
                        "error": None,
                    }
                )
            # Enrich the failed records with their real error text (capped — 1 call each).
            failed = [m for m in out if m["status"] in _ERROR_STATUSES][:15]
            for m in failed:
                m["error"] = await self._error_information(client, m["message_guid"])
        return out

    async def _error_information(self, client: httpx.AsyncClient, guid: str) -> str | None:
        """Plain-text error for a failed message (best-effort, never raises)."""
        if not guid:
            return None
        try:
            token = await self._access_token(client)
            url = (f"{self.base_url}/api/v1/MessageProcessingLogs('{guid}')"
                   "/ErrorInformation/$value")
            r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            if r.status_code >= 400:
                return None
            text = (r.text or "").strip().replace("\n", " ")
            return text[:240] or None
        except Exception:  # noqa: BLE001
            return None

    async def runtime_artifacts(self) -> list[RuntimeArtifact]:
        params = {"$select": "Id,Name,Status", "$top": "1000", "$format": "json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            data = await self._get(client, "IntegrationRuntimeArtifacts", params)
        return [
            {"id": r.get("Id", ""), "name": r.get("Name", ""), "status": (r.get("Status") or "").upper()}
            for r in data.get("d", {}).get("results", [])
        ]

    @staticmethod
    def _parse_jms_broker(data: dict) -> list[dict]:
        """Map a JmsBrokers('Broker1')?$expand=QueueStates payload to queue rows.
        Field names vary across Integration Suite releases, so each value is
        read through a list of aliases."""
        def _first(r: dict, *keys):
            for k in keys:
                if r.get(k) is not None:
                    return r[k]
            return None

        def _int(v) -> int:
            try:
                return int(float(v))
            except Exception:  # noqa: BLE001
                return 0

        d = data.get("d", data) if isinstance(data, dict) else {}
        qs = d.get("QueueStates", d.get("Queues", {})) if isinstance(d, dict) else {}
        rows = qs.get("results", qs) if isinstance(qs, dict) else qs
        if not isinstance(rows, list):
            return []
        out: list[dict] = []
        for r in rows:
            name = _first(r, "QueueName", "Name", "Queue") or ""
            if not name:
                continue
            entries = _int(_first(r, "NumberOfMessages", "Messages", "MessageCount", "numberOfMessages", "Entries"))
            capacity = _int(_first(r, "Capacity", "MaxCapacity", "MaxNumberOfMessages")) or 100
            state_raw = str(_first(r, "State", "QueueState", "Status") or "").strip()
            access = str(_first(r, "AccessType", "Access") or "")
            running = state_raw.lower() in ("", "started", "running", "ok", "active")
            if not running:
                state = state_raw.upper()          # genuinely stopped/errored — surface it
            elif entries >= capacity:
                state = "ATTENTION"                # running but at/over capacity
            else:
                state = "OK"
            out.append({
                "name": name, "depth": entries, "capacity": capacity,
                "stuck": _int(_first(r, "StuckMessages", "Stuck")),
                "retry": _int(_first(r, "RetryMessages", "Retry")),
                "state": state,
                "access": access or "Non-Exclusive",
            })
        return out

    async def jms_queues(self) -> list[dict]:
        """Live JMS message queues via the OData JmsBrokers entity.

          GET /api/v1/JmsBrokers('Broker1')?$expand=QueueStates

        If the tenant has no JMS broker the call 404s and we return []
        (no fabricated rows)."""
        params = {"$expand": "QueueStates", "$format": "json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                data = await self._get(client, "JmsBrokers('Broker1')", params)
            except Exception:  # noqa: BLE001
                return []
        return self._parse_jms_broker(data)

    async def data_stores(self) -> list[dict]:
        """Live CPI Data Stores via the OData v2 DataStores entity (read-only).

        The DataStores entity does not support $top (HTTP 400), so no paging
        options are sent."""
        params = {"$format": "json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            data = await self._get(client, "DataStores", params)
        out: list[dict] = []
        for r in data.get("d", {}).get("results", []):
            out.append({
                "name": r.get("DataStoreName", "") or r.get("Name", ""),
                "iflow": r.get("IntegrationFlow", "") or "",
                "type": r.get("Visibility", "") or r.get("Type", "") or "Global",
                "entries": int(float(r.get("NumberOfMessages", 0) or 0)),
                "overdue": int(float(r.get("NumberOfOverdueMessages", 0) or 0)),
            })
        return out

    async def integration_packages(self) -> list[dict]:
        # NOTE: the design-time OData API does NOT support $select (returns HTTP 501).
        params = {"$format": "json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            data = await self._get(client, "IntegrationPackages", params)
        return [
            {"id": r.get("Id", ""), "name": r.get("Name", ""), "vendor": r.get("Vendor", "")}
            for r in data.get("d", {}).get("results", [])
        ]

    async def package_iflows(self, package_id: str) -> list[dict]:
        path = f"IntegrationPackages('{package_id}')/IntegrationDesigntimeArtifacts"
        params = {"$format": "json"}   # $select unsupported on design-time API
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            data = await self._get(client, path, params)
        return [
            {"id": r.get("Id", ""), "name": r.get("Name", ""), "version": r.get("Version", "")}
            for r in data.get("d", {}).get("results", [])
        ]

    # ---- writes (controlled) ----
    async def _csrf(self, client: httpx.AsyncClient, token: str) -> str:
        """Fetch a CSRF token (and session cookies on the shared client)."""
        r = await client.get(
            f"{self.base_url}/api/v1/",
            headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": "Fetch",
                     "Accept": "application/json"},
        )
        return r.headers.get("x-csrf-token") or r.headers.get("X-CSRF-Token") or ""

    async def add_iflow_to_tenant(self, package_id: str, iflow_id: str, iflow_name: str,
                                  zip_bytes: bytes, deploy: bool = True) -> dict:
        """Create the iFlow design-time artifact in a package, then optionally
        deploy it. Returns {created, deployed, detail}. Mutating — controlled."""
        import base64

        if not package_id:
            raise RuntimeError("No package selected — choose a target package before deploying.")
        content = base64.b64encode(zip_bytes).decode()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            token = await self._access_token(client)
            csrf = await self._csrf(client, token)
            body = {"Name": iflow_name, "Id": iflow_id, "PackageId": package_id,
                    "ArtifactContent": content}
            r = await client.post(
                f"{self.base_url}/api/v1/IntegrationDesigntimeArtifacts",
                json=body,
                headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf,
                         "Content-Type": "application/json", "Accept": "application/json"},
            )
            if r.status_code >= 400:
                raise RuntimeError(f"create iFlow → HTTP {r.status_code}: {r.text[:300]}")
            result = {"created": True, "deployed": False, "detail": f"Created '{iflow_id}' in {package_id}."}

            if deploy:
                csrf2 = await self._csrf(client, token)  # token is single-use per mutation
                dr = await client.post(
                    f"{self.base_url}/api/v1/DeployIntegrationDesigntimeArtifact"
                    f"?Id='{iflow_id}'&Version='active'",
                    headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf2,
                             "Accept": "application/json"},
                )
                if dr.status_code >= 400:
                    result["detail"] += (f" Deploy deferred — HTTP {dr.status_code}: "
                                         f"{dr.text[:200]} (artifact is saved in the package; "
                                         "configure adapters in the Web IDE and deploy there).")
                else:
                    result["deployed"] = True
                    result["detail"] += " Deployment triggered."
            return result

    async def download_iflow(self, iflow_id: str, version: str = "active") -> bytes:
        """Design-time artifact payload is a ZIP (contains the .iflw)."""
        token = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            token = await self._access_token(client)
            url = (f"{self.base_url}/api/v1/IntegrationDesigntimeArtifacts"
                   f"(Id='{iflow_id}',Version='{version}')/$value")
            r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            return r.content
