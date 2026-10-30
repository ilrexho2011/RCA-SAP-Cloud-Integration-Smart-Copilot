"""Demo connector — bundled data so the platform runs without a real tenant.

Numbers mirror the QDKEP Control Room reference (51 completed, 53 deployed
iFlows on the CPI-RCMO tenant) plus representative S/4HANA failures, so the
Monitoring view looks real before a service key is configured.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .base import MplRecord, RuntimeArtifact

_NOW = datetime.now(timezone.utc)


def _ts(minutes_ago: int) -> str:
    return (_NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class DemoConnector:
    kind = "CPI"

    def __init__(self, name: str = "CPI-RCA tenant", sap_sid: str = "CPI") -> None:
        self.name = name
        self.sap_sid = sap_sid
        self.live = False

    async def ping(self) -> tuple[bool, str]:
        return True, "Demo mode — serving bundled RCMO sample data (no tenant configured)."

    async def message_processing_logs(self, hours: int = 24) -> list[MplRecord]:
        completed = [
            {"message_guid": f"demo-ok-{i}", "status": "COMPLETED",
             "integration_flow": "OrderReplication_S4toCPI", "log_end": _ts(i * 5), "error": None}
            for i in range(51)
        ]
        failed = [
            {"message_guid": "demo-f-1", "status": "FAILED", "integration_flow": "S4H_RFC_CONN_ERROR",
             "log_end": _ts(12), "error": "qRFC inbound queue stuck, connection error to partner"},
            {"message_guid": "demo-f-2", "status": "FAILED", "integration_flow": "S4H_TRFC_SYSFAIL",
             "log_end": _ts(34), "error": "qRFC inbound queue ORDERS_IN stopped for hours"},
            {"message_guid": "demo-f-3", "status": "FAILED", "integration_flow": "S4H_ABAP_DUMP_MESSAGE_TYPE_X",
             "log_end": _ts(58), "error": "ABAP dump authorization missing object S_TCODE"},
            {"message_guid": "demo-f-4", "status": "FAILED", "integration_flow": "S4H_ABAP_DUMP_TIME_OUT",
             "log_end": _ts(77), "error": "ABAP dump TIME_OUT runtime error in ZPROGRAM, time limit exceeded"},
        ]
        return completed + failed  # type: ignore[return-value]

    async def runtime_artifacts(self) -> list[RuntimeArtifact]:
        return [
            {"id": f"iflow_{i}", "name": f"DeployedFlow_{i}", "status": "STARTED"}
            for i in range(53)
        ]

    async def connected_systems(self) -> list[dict]:
        """CPI + APIM + AEM as distinct sources, each with its own metrics."""
        from .apim import reference_analytics
        return [
            {
                "name": "CPI-RCA tenant", "sap_sid": "CPI", "kind": "CPI", "live": False,
                "success": 51, "failed": 4, "retry": 0, "total": 55, "deployed_iflows": 53,
                "metrics": [
                    {"label": "Success mes.", "value": 51, "tone": "success"},
                    {"label": "Failed mes.", "value": 4, "tone": "failed"},
                    {"label": "Retry mes.", "value": 0, "tone": "watched"},
                    {"label": "Total mes.", "value": 55, "tone": "info"},
                    {"label": "Deployed iFlows", "value": 53, "tone": "info"},
                ],
            },
            {
                "name": "APIM-RCA (API Management)", "sap_sid": "CPI·APIM", "kind": "APIM", "live": False,
                "success": 14, "failed": 8, "retry": 0, "total": 22, "deployed_iflows": 21,
                "metrics": [
                    {"label": "API proxies", "value": 21, "tone": "info"},
                    {"label": "Deployed", "value": 21, "tone": "success"},
                    {"label": "Success", "value": 14, "tone": "success"},
                    {"label": "Error rate 4xx/5xx", "value": 36, "tone": "failed"},
                    {"label": "Policy faults", "value": 36, "tone": "warn"},
                    {"label": "Avg latency (ms)", "value": 68, "tone": "watched"},
                ],
                "analytics": reference_analytics(),
            },
            {
                "name": "AEM-RCA (Event Mesh)", "sap_sid": "CPI·AEM", "kind": "AEM", "live": False,
                "success": 5299, "failed": 1, "retry": 5, "total": 5300, "deployed_iflows": 8,
                "metrics": [
                    {"label": "Queues", "value": 8, "tone": "info"},
                    {"label": "Events (24h)", "value": 5300, "tone": "info"},
                    {"label": "Spooled", "value": 3, "tone": "warn"},
                    {"label": "Dead-lettered", "value": 1, "tone": "failed"},
                    {"label": "Redelivered", "value": 5, "tone": "watched"},
                ],
            },
        ]

    async def apim_analytics(self) -> dict:
        """Full APIM monitoring indicators (reference set) for the six zones."""
        from .apim import reference_analytics
        return reference_analytics()

    async def apim_proxies(self) -> list[dict]:
        """Demo APIM proxy drill-down rows, derived from the reference breakdown."""
        from .apim import reference_analytics
        bd = reference_analytics()["api_proxy_breakdown"]
        return [{"name": b["name"], "version": "1.0", "status": "deployed",
                 "calls": b["total"], "success": b["success"], "failed": b["failed"]} for b in bd]

    async def jms_queues(self) -> list[dict]:
        return [
            {"name": "OrdersIn", "depth": 0, "capacity": 100, "stuck": 0, "retry": 0, "state": "OK", "access": "Non-Exclusive"},
            {"name": "InvoiceOut", "depth": 12, "capacity": 100, "stuck": 0, "retry": 2, "state": "OK", "access": "Non-Exclusive"},
            {"name": "ShipmentEvents", "depth": 34, "capacity": 100, "stuck": 0, "retry": 1, "state": "OK", "access": "Non-Exclusive"},
            {"name": "RetryQueue", "depth": 7, "capacity": 100, "stuck": 0, "retry": 7, "state": "ATTENTION", "access": "Non-Exclusive"},
            {"name": "Inbound.JMS_DLQ", "depth": 66, "capacity": 100, "stuck": 3, "retry": 0, "state": "ATTENTION", "access": "Non-Exclusive"},
        ]

    async def data_stores(self) -> list[dict]:
        return [
            {"name": "OrderStore", "iflow": "OrderReplication_S4toCPI", "type": "Global", "entries": 128, "overdue": 3},
            {"name": "InvoiceStaging", "iflow": "Invoice_Sync", "type": "Global", "entries": 54, "overdue": 0},
            {"name": "IdempotentKeys", "iflow": "HTTP_JSON_to_OData", "type": "Local", "entries": 512, "overdue": 0},
            {"name": "DeliveryRetry", "iflow": "ShipmentNotify", "type": "Global", "entries": 9, "overdue": 2},
        ]

    async def integration_packages(self) -> list[dict]:
        return [
            {"id": "CPICopilot", "name": "CPI Copilot", "vendor": "RCA"},
            {"id": "OrderToCash", "name": "Order to Cash", "vendor": "RCMO"},
        ]

    async def package_iflows(self, package_id: str) -> list[dict]:
        data = {
            "CPICopilot": [
                {"id": "SF_OrderToS4", "name": "Orders to S/4HANA", "version": "1.0.3"},
                {"id": "HTTP_JSON_to_OData", "name": "HTTP JSON to OData", "version": "1.2.0"},
            ],
            "OrderToCash": [
                {"id": "Invoice_Sync", "name": "Invoice Sync", "version": "2.1.0"},
            ],
        }
        return data.get(package_id, [])
