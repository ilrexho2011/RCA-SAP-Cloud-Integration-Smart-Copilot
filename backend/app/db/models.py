"""ORM models. Secrets are stored AES-256-GCM encrypted (never plaintext)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _uid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(String(255), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="admin")  # admin | member
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class CpiConnection(Base):
    __tablename__ = "cpi_connections"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_conn_tenant"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    base_url: Mapped[str] = mapped_column(String(500), default="")
    token_url: Mapped[str] = mapped_column(String(500), default="")
    client_id: Mapped[str] = mapped_column(String(500), default="")
    secret_enc: Mapped[str] = mapped_column(Text, default="")
    web_ide_url: Mapped[str] = mapped_column(String(500), default="")
    mode: Mapped[str] = mapped_column(String(10), default="live")
    rt_base_url: Mapped[str] = mapped_column(String(500), default="")
    rt_token_url: Mapped[str] = mapped_column(String(500), default="")
    rt_client_id: Mapped[str] = mapped_column(String(500), default="")
    rt_secret_enc: Mapped[str] = mapped_column(Text, default="")


class AiEngine(Base):
    __tablename__ = "ai_engines"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_ai_tenant"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30), default="stub")
    endpoint: Mapped[str] = mapped_column(String(500), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    key_enc: Mapped[str] = mapped_column(Text, default="")


class EmailConfig(Base):
    __tablename__ = "email_configs"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_email_tenant"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    method: Mapped[str] = mapped_column(String(10), default="rca")
    smtp_host: Mapped[str] = mapped_column(String(255), default="")
    smtp_port: Mapped[str] = mapped_column(String(10), default="")
    from_address: Mapped[str] = mapped_column(String(255), default="")
    smtp_user: Mapped[str] = mapped_column(String(255), default="")
    pass_enc: Mapped[str] = mapped_column(Text, default="")
    recipients: Mapped[str] = mapped_column(Text, default="")


class WatchedFlow(Base):
    __tablename__ = "watched_flows"
    __table_args__ = (UniqueConstraint("tenant_id", "iflow_id", name="uq_watch_tenant_iflow"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    iflow_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class IntegrationSource(Base):
    """Live config for an APIM or AEM source (in addition to CPI)."""
    __tablename__ = "integration_sources"
    __table_args__ = (UniqueConstraint("tenant_id", "kind", name="uq_source_tenant_kind"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))          # APIM | AEM
    enabled: Mapped[bool] = mapped_column(default=False)
    auth_type: Mapped[str] = mapped_column(String(10), default="oauth")  # oauth | basic
    base_url: Mapped[str] = mapped_column(String(500), default="")       # API portal / SEMP host
    token_url: Mapped[str] = mapped_column(String(500), default="")
    client_id: Mapped[str] = mapped_column(String(500), default="")
    username: Mapped[str] = mapped_column(String(255), default="")
    secret_enc: Mapped[str] = mapped_column(Text, default="")            # client_secret or password
    extra: Mapped[dict] = mapped_column(JSON, default=dict)              # {"vpn": "..."} for AEM


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="generate")
    status: Mapped[str] = mapped_column(String(30), default="")
    state: Mapped[str] = mapped_column(String(30), default="")
    request: Mapped[dict] = mapped_column(JSON, default=dict)
    classification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    brief: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
