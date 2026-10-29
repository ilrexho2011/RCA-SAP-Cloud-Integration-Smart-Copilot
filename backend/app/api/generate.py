"""Generate API — drive the orchestrator and expose run traces."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import Principal, current_principal
from ..config import Settings, get_settings
from ..models.schemas import GenerateRequest, ReviseRequest, RunView
from ..orchestrator import engine
from ..orchestrator.state import Run

router = APIRouter(prefix="/api/generate", tags=["generate"])


def _view(run: Run) -> RunView:
    return RunView(
        run_id=run.run_id,
        status=run.status.value,
        state=run.state.value,
        steps=[
            {"state": s.state, "label": s.label, "status": s.status,
             "detail": s.detail, "payload": s.payload}
            for s in run.steps
        ],
        classification=run.classification,
        citations=[{"doc_id": c["doc_id"], "title": c["title"]} for c in run.context],
        brief=run.brief,
        artifact=run.artifact,
        validation=run.validation,
        score=run.score,
        attempts=run.attempts,
    )


@router.post("/iflow", response_model=RunView)
async def generate_iflow(req: GenerateRequest, p: Principal = Depends(current_principal),
                         settings: Settings = Depends(get_settings)) -> RunView:
    try:
        run = await engine.start_generate(settings, p.tenant_id, req.model_dump())
    except Exception as e:  # noqa: BLE001
        # Surface the real cause (e.g. AI provider auth/model/network error)
        # instead of an opaque 500, so the UI can show what to fix.
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}")
    return _view(run)


@router.get("/runs/{run_id}", response_model=RunView)
async def get_run(run_id: str, p: Principal = Depends(current_principal)) -> RunView:
    run = engine.get_run(run_id)
    if not run or run.tenant_id != p.tenant_id:
        raise HTTPException(404, "run not found")
    return _view(run)


@router.post("/runs/{run_id}/approve", response_model=RunView)
async def approve(run_id: str, p: Principal = Depends(current_principal)) -> RunView:
    try:
        run = await engine.approve(p.tenant_id, run_id)
    except KeyError:
        raise HTTPException(404, "run not found")
    return _view(run)


@router.post("/runs/{run_id}/deploy", response_model=RunView)
async def deploy(run_id: str, p: Principal = Depends(current_principal),
                 settings: Settings = Depends(get_settings)) -> RunView:
    try:
        run = await engine.deploy(settings, p.tenant_id, run_id)
    except KeyError:
        raise HTTPException(404, "run not found")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Deploy failed: {e}")
    return _view(run)


@router.post("/runs/{run_id}/revise", response_model=RunView)
async def revise(run_id: str, body: ReviseRequest, p: Principal = Depends(current_principal),
                 settings: Settings = Depends(get_settings)) -> RunView:
    try:
        run = await engine.revise(settings, p.tenant_id, run_id, body.feedback)
    except KeyError:
        raise HTTPException(404, "run not found")
    return _view(run)
