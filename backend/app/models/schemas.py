"""Pydantic response contracts for the monitoring API."""
from __future__ import annotations

from pydantic import BaseModel


class KpiCard(BaseModel):
    key: str
    label: str
    value: int
    tone: str  # failed | success | watched | warn | info
    note: str


class SystemKpi(BaseModel):
    label: str
    value: int
    tone: str


class ConnectedSystem(BaseModel):
    name: str
    sap_sid: str
    kind: str  # CPI | APIM | AEM
    live: bool
    success: int
    failed: int
    retry: int
    total: int
    deployed_iflows: int
    metrics: list[SystemKpi] = []   # per-system labelled metrics (varies by kind)
    note: str = ""                  # state note when a configured source is disabled/erroring
    analytics: dict | None = None   # APIM: the six monitoring zones (shown inline below the bar)


class FailedMessage(BaseModel):
    interface: str
    exception: str
    status: str
    error: str
    timestamp: str | None = None


class MonitoringOverview(BaseModel):
    source: str  # "live" | "demo"
    sources_connected: int
    kpis: list[KpiCard]
    systems: list[ConnectedSystem]
    failed_messages: list[FailedMessage]
    error: str | None = None   # populated when a live call fails (scope, network, auth)


class ConnectionTestResult(BaseModel):
    ok: bool
    mode: str  # live | demo
    detail: str
    deployed_iflows: int | None = None


class ConnectionInfo(BaseModel):
    """Non-secret view of the stored connection. Secret is never returned."""
    configured: bool
    mode: str  # live | demo
    base_url: str = ""
    token_url: str = ""
    client_id: str = ""
    web_ide_url: str = ""
    secret_set: bool = False
    # CPI Runtime (Fix/Verify)
    rt_base_url: str = ""
    rt_token_url: str = ""
    rt_client_id: str = ""
    rt_secret_set: bool = False


class ConnectionUpdate(BaseModel):
    base_url: str = ""
    token_url: str = ""
    client_id: str = ""
    web_ide_url: str = ""
    # "__stored__" (or empty) keeps the existing secret; any other value replaces it.
    client_secret: str = "__stored__"
    mode: str = "live"
    # CPI Runtime (optional)
    rt_base_url: str = ""
    rt_token_url: str = ""
    rt_client_id: str = ""
    rt_client_secret: str = "__stored__"


class EmailAlertsInfo(BaseModel):
    configured: bool
    method: str = "rca"   # rca | smtp
    smtp_host: str = ""
    smtp_port: str = ""
    from_address: str = ""
    smtp_user: str = ""
    recipients: str = ""
    password_set: bool = False


class EmailAlertsUpdate(BaseModel):
    method: str = "rca"
    smtp_host: str = ""
    smtp_port: str = ""
    from_address: str = ""
    smtp_user: str = ""
    smtp_password: str = "__stored__"
    recipients: str = ""


class EmailTestResult(BaseModel):
    ok: bool
    detail: str


# ---- APIM / AEM sources ----

class SourceInfo(BaseModel):
    kind: str                 # APIM | AEM
    enabled: bool = False
    auth_type: str = "oauth"  # oauth | basic
    base_url: str = ""
    token_url: str = ""
    client_id: str = ""
    username: str = ""
    vpn: str = ""             # AEM message VPN
    analytics_base_url: str = ""   # APIM AnalyticsService base (optional)
    secret_set: bool = False


class SourceUpdate(BaseModel):
    enabled: bool = False
    auth_type: str = "oauth"
    base_url: str = ""
    token_url: str = ""
    client_id: str = ""
    username: str = ""
    vpn: str = ""
    analytics_base_url: str = ""
    secret: str = "__stored__"


class SourceTestResult(BaseModel):
    ok: bool
    kind: str
    detail: str


# ---- Orchestrator / Generate ----

class Attachment(BaseModel):
    name: str
    kind: str = "text"     # groovy | xml | json | xslt | xsd | iflw | zip | image | text
    content: str = ""      # text content (or note for binary/image)


class GenerateRequest(BaseModel):
    description: str
    iflow_id: str = "iFlow"
    iflow_name: str = "iFlow"
    package: str = "CPICopilot"
    sample_input: str = ""
    sample_output: str = ""
    quick: bool = False   # skip the human-approval gate and run straight through
    attachments: list[Attachment] = []


class RunStepView(BaseModel):
    state: str
    label: str
    status: str
    detail: str
    payload: dict | None = None


class RunView(BaseModel):
    run_id: str
    status: str
    state: str
    steps: list[RunStepView]
    classification: dict | None = None
    citations: list[dict] = []
    brief: dict | None = None
    artifact: str | None = None
    validation: dict | None = None
    score: dict | None = None
    attempts: int = 0


class ReviseRequest(BaseModel):
    feedback: str


# ---- AI engine (BYOK) ----

class AiEngineInfo(BaseModel):
    provider: str          # stub | openai | azure | anthropic | gemini | deepseek
    endpoint: str = ""
    model: str = ""
    key_set: bool = False
    active: bool = False    # a real provider is configured and in use


class AiEngineUpdate(BaseModel):
    provider: str = "stub"
    endpoint: str = ""
    model: str = ""
    api_key: str = "__stored__"   # sentinel keeps existing key


class AiEngineTestResult(BaseModel):
    ok: bool
    provider: str
    detail: str


# ---- iFlows / Explain ----

class ExplainResult(BaseModel):
    source: str            # zip | tenant | demo
    facts: dict
    summary: str
    risks: list[str] = []
    # Model-grade narrative (What it does / Trigger / Step-by-step / Groovy
    # scripts / Error handling / Notes). Optional for backward compatibility.
    sections: dict | None = None
    scripts: list[dict] = []   # [{name, points:[...]}]  — grounded in the real code


# ---- Groovy ----

class GroovyRequest(BaseModel):
    description: str


class GroovyResult(BaseModel):
    steps: list[dict]
    script: str
    validation: dict
