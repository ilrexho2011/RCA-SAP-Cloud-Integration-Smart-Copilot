"""Deterministic orchestration engine.

Runs the generation state machine, pausing at human-in-the-loop gates. Control
transitions live in code (deterministic); the LLM is only invoked *inside*
steps (classify, plan). Every step is recorded for the run trace.

Flow:
  classify → retrieve → plan → draft_brief → [AWAIT_APPROVAL]
    approve → generate → validate → quality_gate
                                     ├─ pass → [AWAIT_DEPLOY]
                                     └─ fail → repair → validate (≤ MAX_ATTEMPTS)
                                                        else → BLOCKED
"""
from __future__ import annotations

import uuid

from ..config import Settings
from ..db import repos
from ..llm.provider import get_provider
from . import agents, quality
from .state import Run, RunState, RunStatus
from .validators import validate_iflow

MAX_ATTEMPTS = 3

_RUNS: dict[str, Run] = {}


def get_run(run_id: str) -> Run | None:
    return _RUNS.get(run_id)


def _attachments_text(attachments: list[dict]) -> str:
    """Fold uploaded descriptive files into a compact grounding string."""
    parts = []
    for a in attachments[:12]:
        name = a.get("name", "file")
        kind = a.get("kind", "text")
        content = (a.get("content", "") or "")[:4000]
        if kind in ("image", "zip", "iflw") and not content:
            parts.append(f"[{kind}] {name} (binary attachment — provided as context reference)")
        else:
            parts.append(f"[{kind}] {name}:\n{content}")
    return "\n\n".join(parts)


def _to_dict(run: Run) -> dict:
    return {
        "run_id": run.run_id, "status": run.status.value, "state": run.state.value,
        "request": run.request, "classification": run.classification,
        "citations": [{"doc_id": c["doc_id"], "title": c["title"]} for c in run.context],
        "brief": run.brief, "artifact": run.artifact, "validation": run.validation,
        "score": run.score,
        "steps": [{"state": s.state, "label": s.label, "status": s.status,
                   "detail": s.detail, "payload": s.payload} for s in run.steps],
        "attempts": run.attempts,
    }


async def _persist(run: Run) -> None:
    # Persistence is best-effort: a run trace failing to serialize/save must not
    # turn a successful generation into a 500. The in-memory run still serves.
    if not run.tenant_id:
        return
    try:
        await repos.save_run(run.tenant_id, _to_dict(run))
    except Exception as e:  # noqa: BLE001
        run.add_step(run.state, "Persist run trace", status="info",
                     detail=f"Run kept in memory; not saved: {e}")


async def start_generate(settings: Settings, tenant_id: str, request: dict) -> Run:
    run = Run(run_id=uuid.uuid4().hex[:12], request=request, tenant_id=tenant_id)
    _RUNS[run.run_id] = run
    provider = await get_provider(settings, tenant_id)
    description = request.get("description", "")
    s_in = request.get("sample_input", "")
    s_out = request.get("sample_output", "")
    att_text = _attachments_text(request.get("attachments", []))

    # 1) classify
    run.state = RunState.CLASSIFY
    run.classification = await agents.classify(provider, description, s_in, s_out, att_text)
    run.add_step(RunState.CLASSIFY, "Classify integration",
                 detail=f"{run.classification.get('sender')} → {run.classification.get('receiver')}",
                 payload=run.classification)

    # 2) retrieve (RAG grounding)
    run.state = RunState.RETRIEVE
    run.context = agents.retrieve_context(description, run.classification)
    run.add_step(RunState.RETRIEVE, "Retrieve patterns (RAG)",
                 detail=f"{len(run.context)} patterns",
                 payload={"citations": [{"doc_id": c["doc_id"], "title": c["title"]} for c in run.context]})

    # 3) plan + 4) draft brief
    run.state = RunState.PLAN
    run.brief = await agents.plan(provider, description, run.classification, run.context, s_in, s_out, att_text)
    atts = request.get("attachments", [])
    if s_in or s_out or atts:
        run.brief["samples"] = {"input": bool(s_in), "output": bool(s_out),
                                "attachments": [a.get("name", "") for a in atts]}
    run.add_step(RunState.PLAN, "Plan design", detail=run.brief.get("summary", ""))
    run.add_step(RunState.DRAFT_BRIEF, "Draft design brief",
                 detail=f"{len(run.brief.get('steps', []))} steps", payload=run.brief)

    # Quick Generate: skip the approval gate and run straight through.
    if request.get("quick"):
        run.add_step(RunState.DRAFT_BRIEF, "Quick Generate — auto-approving brief", status="info",
                     detail="HITL skipped by request; write to tenant still requires approval.")
        run.status = RunStatus.RUNNING
        await _generate_and_gate(run)
        return run

    # HITL gate 1
    run.state = RunState.AWAIT_APPROVAL
    run.status = RunStatus.AWAITING_APPROVAL
    run.add_step(RunState.AWAIT_APPROVAL, "Awaiting human approval", status="info",
                 detail="Review the design brief, then approve or revise.")
    await _persist(run)
    return run


async def revise(settings: Settings, tenant_id: str, run_id: str, feedback: str) -> Run:
    run = _require(run_id)
    if run.tenant_id != tenant_id:
        raise KeyError(run_id)
    run.request["description"] = f"{run.request.get('description','')}\n\nRevision: {feedback}"
    _RUNS.pop(run_id, None)
    return await start_generate(settings, tenant_id, run.request)


async def deploy(settings: Settings, tenant_id: str, run_id: str) -> Run:
    """Write the generated iFlow to the live CPI tenant (create in package +
    attempt activation). Controlled mutation — only runs on the deploy gate."""
    run = _require(run_id)
    if run.tenant_id != tenant_id:
        raise KeyError(run_id)
    if run.status != RunStatus.AWAITING_DEPLOY:
        return run

    from ..services.connection import resolve_connector
    from ..iflow.packager import build_iflow_zip

    conn = await resolve_connector(settings, tenant_id)
    if not getattr(conn, "live", False) or not hasattr(conn, "add_iflow_to_tenant"):
        raise RuntimeError("No live CPI connection configured — set and test it in Settings first.")

    req = run.request
    iflow_id = req.get("iflow_id", "iFlow")
    iflow_name = req.get("iflow_name", iflow_id)
    package_id = req.get("package", "")
    run.state = RunState.AWAIT_DEPLOY
    run.add_step(RunState.AWAIT_DEPLOY, "Deploy to tenant — packaging",
                 status="info", detail=f"iFlow {iflow_id} → package {package_id}")

    zip_bytes = build_iflow_zip(iflow_id, iflow_name, run.artifact or "",
                                resources=req.get("attachments") or [])
    res = await conn.add_iflow_to_tenant(package_id, iflow_id, iflow_name, zip_bytes, deploy=True)

    run.status = RunStatus.DONE
    run.state = RunState.DONE
    run.add_step(RunState.DONE, "Deployed to tenant",
                 status="ok" if res.get("created") else "fail",
                 detail=res.get("detail", ""), payload=res)
    await _persist(run)
    return run


async def approve(tenant_id: str, run_id: str) -> Run:
    run = _require(run_id)
    if run.tenant_id != tenant_id:
        raise KeyError(run_id)
    if run.status != RunStatus.AWAITING_APPROVAL:
        return run
    run.status = RunStatus.RUNNING
    await _generate_and_gate(run)
    return run


async def _generate_and_gate(run: Run) -> None:
    req = run.request
    # 5) generate
    run.state = RunState.GENERATE
    run.attempts += 1
    run.artifact = agents.generate_iflow(
        req.get("iflow_id", "iFlow"), req.get("iflow_name", "iFlow"),
        run.classification or {}, run.brief or {},
    )
    run.add_step(RunState.GENERATE, "Generate iFlow (BPMN2)",
                 detail=f"attempt {run.attempts}", payload={"bytes": len(run.artifact)})

    # 6) validate + 7) quality gate (with repair loop)
    while True:
        run.state = RunState.VALIDATE
        v = validate_iflow(run.artifact or "")
        run.validation = {"ok": v.ok, "checks": v.checks}
        run.add_step(RunState.VALIDATE, "Validate artifact",
                     status="ok" if v.ok else "fail",
                     detail=f"{sum(c['passed'] for c in v.checks)}/{len(v.checks)} checks",
                     payload=run.validation)

        run.state = RunState.QUALITY_GATE
        run.score = quality.score(v, run.brief or {})
        run.add_step(RunState.QUALITY_GATE, "Quality gate",
                     status="ok" if run.score["passed"] else "fail",
                     detail=f"{run.score['total']}/100 · {run.score['status']}",
                     payload=run.score)

        if run.score["passed"]:
            run.state = RunState.AWAIT_DEPLOY
            run.status = RunStatus.AWAITING_DEPLOY
            run.add_step(RunState.AWAIT_DEPLOY, "Awaiting deploy approval", status="info",
                         detail="Passed the gate. Human approval required before writing to the tenant.")
            await _persist(run)
            return

        if run.attempts >= MAX_ATTEMPTS:
            run.state = RunState.BLOCKED
            run.status = RunStatus.BLOCKED
            run.add_step(RunState.BLOCKED, "Blocked", status="fail",
                         detail=f"Gate not met after {run.attempts} attempts.")
            await _persist(run)
            return

        # 6b) repair and retry
        run.state = RunState.REPAIR
        run.attempts += 1
        run.add_step(RunState.REPAIR, "Repair & regenerate", status="info",
                     detail=f"attempt {run.attempts}")
        run.artifact = agents.generate_iflow(
            req.get("iflow_id", "iFlow"), req.get("iflow_name", "iFlow"),
            run.classification or {}, run.brief or {},
        )


def _require(run_id: str) -> Run:
    run = _RUNS.get(run_id)
    if not run:
        raise KeyError(run_id)
    return run
