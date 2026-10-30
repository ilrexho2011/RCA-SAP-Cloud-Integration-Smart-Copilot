"""Orchestrated Groovy generation: analyze → generate → validate."""
from __future__ import annotations

from ..config import Settings
from ..groovy import generator, validator
from ..llm.provider import get_provider


async def generate_script(settings: Settings, tenant_id: str, description: str) -> dict:
    provider = await get_provider(settings, tenant_id)
    steps = [{"state": "analyze", "label": "Analyze intent", "status": "ok",
              "detail": f"provider={provider.name}"}]

    code = await generator.generate(provider, description)
    steps.append({"state": "generate", "label": "Generate Groovy", "status": "ok",
                  "detail": f"{len(code)} chars"})

    v = validator.validate(code)
    steps.append({"state": "validate", "label": "Validate",
                  "status": "ok" if v.ok else "fail",
                  "detail": f"{sum(c['passed'] for c in v.checks)}/{len(v.checks)} checks"})

    return {"steps": steps, "script": code, "validation": {"ok": v.ok, "checks": v.checks}}
