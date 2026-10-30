"""Run state model for the orchestrator."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class RunState(str, Enum):
    CLASSIFY = "classify"
    RETRIEVE = "retrieve"
    PLAN = "plan"
    DRAFT_BRIEF = "draft_brief"
    AWAIT_APPROVAL = "await_approval"   # HITL gate 1: approve the brief
    GENERATE = "generate"
    VALIDATE = "validate"
    QUALITY_GATE = "quality_gate"
    REPAIR = "repair"
    AWAIT_DEPLOY = "await_deploy"       # HITL gate 2: write to tenant
    BLOCKED = "blocked"                 # failed gate after retries
    DONE = "done"
    ERROR = "error"


class RunStatus(str, Enum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_DEPLOY = "awaiting_deploy"
    BLOCKED = "blocked"
    DONE = "done"
    ERROR = "error"


@dataclass
class RunStep:
    state: str
    label: str
    status: str = "ok"          # ok | fail | info
    detail: str = ""
    started_at: float = field(default_factory=time.time)
    payload: dict | None = None


@dataclass
class Run:
    run_id: str
    request: dict
    tenant_id: str = ""
    status: RunStatus = RunStatus.RUNNING
    state: RunState = RunState.CLASSIFY
    steps: list[RunStep] = field(default_factory=list)
    classification: dict | None = None
    context: list[dict] = field(default_factory=list)
    brief: dict | None = None
    artifact: str | None = None
    validation: dict | None = None
    score: dict | None = None
    attempts: int = 0
    created_at: float = field(default_factory=time.time)

    def add_step(self, state: RunState, label: str, status: str = "ok",
                 detail: str = "", payload: dict | None = None) -> None:
        self.steps.append(RunStep(state=state.value, label=label, status=status,
                                  detail=detail, payload=payload))
