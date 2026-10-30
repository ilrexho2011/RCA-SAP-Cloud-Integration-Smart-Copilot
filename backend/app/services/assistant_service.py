"""AI Assistant — grounded chat over the tenant's live inventory + pattern RAG.

Uses the tenant's BYOK provider when configured; otherwise a deterministic stub
that answers from the live monitoring facts and retrieved patterns (no guessing).
"""
from __future__ import annotations

from ..config import Settings
from ..llm.provider import get_provider
from ..orchestrator import rag
from . import monitoring_service

ASSISTANT_SYS = (
    "You are RCA Smart Copilot's assistant for SAP Cloud Integration (CPI), "
    "API Management (APIM) and Advanced Event Mesh (AEM). Answer concisely and "
    "practically. Ground every operational claim in the LIVE CONTEXT and RETRIEVED "
    "PATTERNS provided below. If the answer is not supported by the context, say so "
    "and suggest how to find it. Do not invent MPL values, adapter names, or endpoints."
)


def _context(ov, patterns: list[dict]) -> str:
    lines = [f"LIVE CONTEXT (source={ov.source}):"]
    for s in ov.systems:
        state = "live" if (s.live and not s.note) else (s.note or "demo")
        mm = ", ".join(f"{m.label}={m.value}" for m in s.metrics) or "no metrics"
        lines.append(f"- {s.kind} {s.name} [{state}]: {mm}")
    if ov.failed_messages:
        lines.append("Recent failed interfaces: " + ", ".join(
            f"{m.interface} ({m.error})" for m in ov.failed_messages[:5]))
    if patterns:
        lines.append("RETRIEVED PATTERNS:")
        for p in patterns:
            lines.append(f"- {p['doc_id']} {p['title']}: {p['snippet']}")
    return "\n".join(lines)


def _kpi(ov, key: str) -> int:
    return next((k.value for k in ov.kpis if k.key == key), 0)


def _stub_reply(question: str, ov, patterns: list[dict]) -> str:
    q = question.lower()
    parts: list[str] = []
    failed, completed = _kpi(ov, "failed"), _kpi(ov, "completed")
    deployed = ov.systems[0].deployed_iflows if ov.systems else 0
    kinds = ", ".join(s.kind for s in ov.systems) or "none"

    if any(k in q for k in ("fail", "error", "complet", "deploy", "system", "proxy",
                            "queue", "how many", "status", "health", "traffic", "latency")):
        parts.append(f"Current status ({ov.source}): {completed} completed and {failed} failed "
                     f"messages in the last 24h across {len(ov.systems)} system(s): {kinds}. "
                     f"{deployed} iFlow(s) deployed on CPI.")
        if ov.failed_messages:
            parts.append("Recent failures: " + "; ".join(
                f"{m.interface} — {m.error}" for m in ov.failed_messages[:3]))
    if patterns:
        p = patterns[0]
        parts.append(f"Relevant SAP CPI pattern — {p['title']} ({p['doc_id']}): {p['snippet']}")
    if not parts:
        parts.append("I can help with SAP CPI, APIM and AEM — design, monitoring and "
                     "troubleshooting. Ask about failures, deployed iFlows, adapters, error "
                     "handling, API traffic, queues, or an integration pattern.")
    parts.append("— RCA Copilot AI (configure a BYOK provider in Settings for fuller, "
                 "reasoning-based answers).")
    return "\n\n".join(parts)


async def chat(settings: Settings, tenant_id: str, messages: list[dict]) -> dict:
    question = ""
    for m in reversed(messages):
        if m.get("role") == "user" and m.get("content"):
            question = m["content"]
            break
    if not question:
        return {"reply": "Ask me anything about SAP CPI, APIM or AEM."}

    ov = await monitoring_service.get_overview(settings, tenant_id)
    patterns = rag.retrieve(question, k=3)
    provider = await get_provider(settings, tenant_id)

    if provider.name == "stub":
        return {"reply": _stub_reply(question, ov, patterns), "grounded": True, "provider": "stub"}

    # Real provider: include a short recent history for continuity.
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages[-6:] if m.get("content"))
    system = f"{ASSISTANT_SYS}\n\n{_context(ov, patterns)}"
    try:
        reply = await provider.complete(system=system, user=history or question, json_mode=False)
        return {"reply": reply.strip(), "grounded": True, "provider": provider.name}
    except Exception as e:  # noqa: BLE001
        return {"reply": f"The AI provider returned an error: {e}", "grounded": False, "provider": provider.name}
