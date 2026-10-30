"""Connector protocol — the read-only surface the monitoring service depends on.

Both the live SAP CPI connector and the demo provider implement this, so the
service layer never branches on environment.
"""
from __future__ import annotations

from typing import Protocol, TypedDict


class MplRecord(TypedDict, total=False):
    message_guid: str
    status: str            # COMPLETED | FAILED | RETRY | PROCESSING | ...
    integration_flow: str
    log_end: str | None
    error: str | None


class RuntimeArtifact(TypedDict, total=False):
    id: str
    name: str
    status: str            # STARTED | ERROR | ...


class CpiConnector(Protocol):
    kind: str              # "CPI"
    name: str
    sap_sid: str
    live: bool

    async def ping(self) -> tuple[bool, str]:
        """Return (ok, human-readable detail)."""
        ...

    async def message_processing_logs(self, hours: int = 24) -> list[MplRecord]:
        """MPL entries within the last ``hours`` window."""
        ...

    async def runtime_artifacts(self) -> list[RuntimeArtifact]:
        """Deployed integration runtime artifacts."""
        ...
