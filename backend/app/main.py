"""RCA Smart Copilot for SAP Cloud Integration — FastAPI entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import assistant, auth, generate, groovy, iflows, kb, monitor, monitoring, settings as settings_api
from .config import get_settings
from .db.base import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="RCA Smart Copilot for SAP Cloud Integration", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(monitoring.router)
app.include_router(monitor.router)
app.include_router(settings_api.router)
app.include_router(generate.router)
app.include_router(iflows.router)
app.include_router(groovy.router)
app.include_router(kb.router)
app.include_router(assistant.router)


@app.get("/api/health")
async def health() -> dict:
    s = get_settings()
    return {"status": "ok", "version": __version__, "env": s.rca_env}
