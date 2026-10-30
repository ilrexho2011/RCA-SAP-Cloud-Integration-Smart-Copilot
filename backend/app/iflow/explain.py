"""Explain a parsed iFlow in plain English, grounded in the parsed facts.

The narrative is built from the model and the real Groovy scripts (no
hallucination). A BYOK provider may elaborate the prose sections, but every
structured fact — adapters, steps, script behaviour — comes only from the
parsed .iflw and the bundled scripts. The output mirrors the reference model:
What it does · Trigger · Step by step · Groovy scripts · Error handling · Notes.
"""
from __future__ import annotations

import json
import re

from ..llm.provider import LLMProvider, StubProvider, parse_json
from .parser import IFlowModel

_KIND_LABEL = {
    "start": "Start", "end": "End", "step": "Step", "service": "Service call",
    "router": "Router (conditional)", "subprocess": "Sub-process",
}

# activityType (SAP ifl:property) → human role
_ACTIVITY_ROLE = {
    "Script": "Groovy script",
    "Enricher": "Content Modifier",
    "ExternalCall": "Request-Reply service call",
    "Mapping": "Message mapping",
    "XSLTMapping": "XSLT mapping",
    "Splitter": "Splitter",
    "Gather": "Gather",
    "OrderedGather": "Gather",
    "Aggregator": "Aggregator",
    "StartTimerEvent": "Start Timer",
    "MessageStartEvent": "Message Start",
}


def build_facts(m: IFlowModel) -> dict:
    step_lines = []
    for s in m.steps:
        label = _KIND_LABEL.get(s["kind"], s["kind"])
        at = f" [{s['activity_type']}]" if s.get("activity_type") else ""
        step_lines.append(f"{label}: {s['name']}{at}")
    return {
        "name": m.name,
        "sender_adapter": m.sender_adapter or "unknown",
        "receiver_adapter": m.receiver_adapter or "unknown",
        "step_count": len(m.steps),
        "steps": step_lines,
        "has_error_handling": m.has_error_handling,
        "participants": m.participants,
    }


def deterministic_summary(facts: dict) -> str:
    parts = [
        f"'{facts['name']}' receives messages via a {facts['sender_adapter']} sender "
        f"and delivers to a {facts['receiver_adapter']} receiver."
    ]
    if facts["step_count"]:
        parts.append(f"It runs {facts['step_count']} process step(s).")
    parts.append(
        "Error handling is defined." if facts["has_error_handling"]
        else "No dedicated error-handling sub-process was detected — consider adding one."
    )
    return " ".join(parts)


# ---- deterministic script analysis (grounded in the real code) ----

def analyze_script(name: str, code: str) -> list[str]:
    """Bullet points describing what a Groovy/JS script does, read from its body."""
    pts: list[str] = []
    c = code

    def names(pattern: str) -> list[str]:
        return sorted({m for m in re.findall(pattern, c)})

    props_set = names(r"setProperty\(\s*['\"]([^'\"]+)['\"]")
    hdrs_set = names(r"setHeader\(\s*['\"]([^'\"]+)['\"]")
    props_read = names(r"getProperty\(\s*['\"]([^'\"]+)['\"]")
    hdrs_read = names(r"getHeader\(\s*['\"]([^'\"]+)['\"]")

    if "JsonSlurper" in c or "parseText" in c:
        pts.append("Parses the incoming body as JSON.")
    if "XmlSlurper" in c or "XmlParser" in c:
        pts.append("Parses the incoming body as XML.")
    if props_read:
        pts.append(f"Reads message propert{'ies' if len(props_read) > 1 else 'y'}: "
                   f"{', '.join(props_read)}.")
    if hdrs_read:
        pts.append(f"Reads header{'s' if len(hdrs_read) > 1 else ''}: {', '.join(hdrs_read)}.")
    if "URLEncoder" in c or "encode(" in c and "URLEncoder" in c:
        pts.append("URL-encodes text before it is used downstream.")
    if "encodeBase64" in c or "Base64" in c:
        pts.append("Base64-encodes/decodes content.")
    if props_set:
        pts.append(f"Sets propert{'ies' if len(props_set) > 1 else 'y'}: {', '.join(props_set)}.")
    if hdrs_set:
        pts.append(f"Sets header{'s' if len(hdrs_set) > 1 else ''}: {', '.join(hdrs_set)}.")
    if re.search(r"setBody\(", c):
        pts.append("Replaces the message body.")
    if "JsonOutput" in c:
        pts.append("Serializes the result back to JSON.")
    if any(k in c for k in ("HttpURLConnection", "openConnection", "new URL(", "RestTemplate")):
        pts.append("Makes an outbound HTTP call from within the script.")
    if "addAttachmentAsString" in c or "getMessageLog" in c:
        pts.append("Writes a log attachment for monitoring/troubleshooting.")
    if "throw new" in c or "throw " in c:
        pts.append("Raises an exception on invalid input to fail the message deliberately.")
    if not pts:
        first = next((ln.strip() for ln in code.splitlines()
                      if ln.strip() and not ln.strip().startswith(("import", "//", "/*", "*"))), "")
        pts.append(f"Custom logic (first statement: {first[:120]})." if first
                   else "Custom script logic.")
    return pts


def _script_verb(scripts: list[dict]) -> str:
    joined = " ".join(s.get("code", "") for s in scripts).lower()
    if "http" in joined or "url" in joined:
        return "builds and sends an HTTP request"
    if "json" in joined:
        return "transforms JSON content"
    if "xml" in joined:
        return "transforms XML content"
    return "applies custom transformation logic"


def build_sections(facts: dict, scripts: list[dict]) -> dict:
    name = facts["name"]
    sender = facts["sender_adapter"]
    receiver = facts["receiver_adapter"]
    steps = facts["steps"]

    # Trigger
    if sender in ("", "unknown"):
        trigger = ("Manually triggered or started by an external process — no sender adapter is "
                   "defined, so it does not start automatically from an external system.")
    else:
        trigger = f"Triggered by messages arriving on the {sender} sender adapter."

    # What it does
    what_bits = []
    if scripts:
        what_bits.append(f"Runs {len(scripts)} Groovy script(s) that {_script_verb(scripts)}")
    if receiver not in ("", "unknown"):
        what_bits.append(f"delivers the result to a {receiver} receiver")
    what = (f"'{name}' processes messages through {facts['step_count']} step(s)"
            + (": " + "; ".join(what_bits) if what_bits else "") + ".")

    # Step by step (prose, grounded in each step's kind / activityType / name)
    step_prose = [_step_sentence(line) for line in steps]

    # Error handling
    eh: list[str] = []
    if facts["has_error_handling"]:
        eh.append("An exception sub-process is defined to catch and handle failures.")
    else:
        eh.append("No exception sub-process was detected — transient failures may not be retried.")
    eh.append("Confirm the receiver adapter's retry and 'throw exception on failure' settings.")

    # Notes
    notes: list[str] = []
    if sender in ("", "unknown"):
        notes.append("No sender adapter suggests this is a test or externally-triggered integration "
                     "rather than one listening on an endpoint.")
    act_types = sorted({re.search(r"\[([^\]]+)\]", ln).group(1) for ln in steps
                        if re.search(r"\[([^\]]+)\]", ln)})
    if act_types:
        notes.append(f"Activity types present: {', '.join(act_types)}.")
    creds = sorted({m for s in scripts for m in
                    re.findall(r"['\"]([A-Za-z0-9_\-]*(?:SMS|Cred|Auth|Token|API)[A-Za-z0-9_\-]*)['\"]",
                               s.get("code", ""))})
    if creds:
        notes.append(f"References credential/parameter name(s): {', '.join(creds[:5])}.")

    return {
        "what_it_does": what,
        "trigger": trigger,
        "step_by_step": step_prose,
        "error_handling": eh,
        "notes": notes,
    }


def _step_sentence(line: str) -> str:
    """Turn a 'Label: name [ActivityType]' line into a readable sentence."""
    at = ""
    m = re.search(r"\[([^\]]+)\]", line)
    if m:
        at = m.group(1)
    head = line.split(":", 1)
    label = head[0].strip()
    rest = head[1].strip() if len(head) > 1 else ""
    nm = re.sub(r"\s*\[[^\]]+\]\s*$", "", rest).strip() or label
    role = _ACTIVITY_ROLE.get(at, label)
    if at == "Script":
        return f"Run {role} '{nm}' to transform or enrich the message."
    if at == "Enricher":
        return f"{role} '{nm}' sets headers/properties or adjusts the body."
    if at == "ExternalCall":
        return f"{role} '{nm}' calls an external system and waits for the reply."
    if at in ("Mapping", "XSLTMapping"):
        return f"{role} '{nm}' converts the source structure to the target structure."
    if label == "Start":
        return f"Start: the process begins ({nm})."
    if label == "End":
        return f"End: the integration process completes ({nm})."
    if label.startswith("Router"):
        return f"Router '{nm}' branches the flow based on conditions."
    return f"{role}: '{nm}'."


_LLM_SYSTEM = (
    "You are a senior SAP Cloud Integration architect. Explain an iFlow for an engineer. "
    "Use ONLY the facts and script bodies provided — never invent adapters, steps, systems or "
    "credentials. Keep it precise and technical. Return STRICT JSON only."
)


async def _llm_sections(provider: LLMProvider, facts: dict, scripts: list[dict]) -> dict | None:
    """Ask a BYOK provider to elaborate the prose sections, grounded in the inputs."""
    payload = {
        "task": "explain_iflow",
        "facts": facts,
        "scripts": [{"name": s["name"], "code": s.get("code", "")[:4000]} for s in scripts],
        "return_json_schema": {
            "what_it_does": "string (1-2 sentences)",
            "trigger": "string",
            "step_by_step": ["string per step, in order"],
            "error_handling": ["string"],
            "notes": ["string"],
        },
    }
    try:
        raw = await provider.complete(_LLM_SYSTEM, json.dumps(payload), json_mode=True)
        data = parse_json(raw)
        # keep only the expected keys and only if non-empty
        out = {}
        for k in ("what_it_does", "trigger", "step_by_step", "error_handling", "notes"):
            v = data.get(k)
            if v:
                out[k] = v
        return out or None
    except Exception:  # noqa: BLE001 — any failure falls back to deterministic
        return None


async def explain(provider: LLMProvider, m: IFlowModel, scripts: list[dict] | None = None) -> dict:
    scripts = scripts or []
    facts = build_facts(m)
    summary = deterministic_summary(facts)

    risks = []
    if not facts["has_error_handling"]:
        risks.append("No exception subprocess — transient failures may not be retried.")
    if facts["receiver_adapter"] == "unknown":
        risks.append("Receiver adapter could not be determined from the model.")

    sections = build_sections(facts, scripts)
    # BYOK enrichment — merge over the deterministic base, per field
    if not isinstance(provider, StubProvider):
        enriched = await _llm_sections(provider, facts, scripts)
        if enriched:
            sections = {**sections, **enriched}

    script_points = [{"name": s["name"], "points": analyze_script(s["name"], s.get("code", ""))}
                     for s in scripts]

    return {"facts": facts, "summary": summary, "risks": risks,
            "sections": sections, "scripts": script_points}
