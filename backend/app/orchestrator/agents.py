"""Specialized agents used by the orchestrator: classify, plan, generate.

Each agent is a thin, testable function that combines RAG grounding with an
LLM call through the provider abstraction. The generate agent emits a BPMN2
iFlow skeleton derived from the approved brief.
"""
from __future__ import annotations

import json
from xml.sax.saxutils import escape

from ..llm.provider import LLMProvider, parse_json
from . import rag

_CLASSIFY_SYS = (
    "You are an SAP CPI integration classifier. Read the integration description "
    "and return ONLY a JSON object with exactly these keys: "
    '{"pattern": string, "sender": string, "receiver": string, '
    '"needs_mapping": boolean, "needs_groovy": boolean}. '
    "Use real SAP adapter names (HTTPS, SOAP, OData, JMS, SFTP, IDoc). Do not invent names."
)

_PLAN_SYS = (
    "You design SAP CPI iFlows grounded ONLY in the provided pattern doc_ids. "
    "Return ONLY a JSON object with exactly these keys: "
    '{"summary": string, "steps": string[], "error_handling": string, "security": string}. '
    "steps must be an ordered list starting with the sender and ending with the receiver."
)


def _augment(description: str, sample_input: str = "", sample_output: str = "",
             attachments: str = "") -> str:
    """Fold sample payloads and uploaded files into the text so classification
    detects mapping/scripting needs and grounds the plan in the attachments."""
    extra = ""
    if sample_input:
        extra += f"\nSample input:\n{sample_input[:2000]}"
    if sample_output:
        extra += f"\nSample output:\n{sample_output[:2000]}"
    if attachments:
        extra += f"\nUploaded files:\n{attachments[:6000]}"
    return description + extra


async def classify(provider: LLMProvider, description: str,
                   sample_input: str = "", sample_output: str = "", attachments: str = "") -> dict:
    out = await provider.complete(
        system=_CLASSIFY_SYS,
        user=json.dumps({"task": "classify",
                         "description": _augment(description, sample_input, sample_output, attachments)}),
        json_mode=True,
    )
    data = parse_json(out)
    data.setdefault("sender", "HTTPS")
    data.setdefault("receiver", "OData")
    data.setdefault("pattern", "point-to-point")
    data.setdefault("needs_mapping", False)
    data.setdefault("needs_groovy", False)
    return data


def retrieve_context(description: str, classification: dict) -> list[dict]:
    query = " ".join(
        [description, classification.get("sender", ""), classification.get("receiver", "")]
        + (["mapping"] if classification.get("needs_mapping") else [])
        + (["groovy"] if classification.get("needs_groovy") else [])
        + ["error handling"]
    )
    return rag.retrieve(query, k=4)


async def plan(provider: LLMProvider, description: str, classification: dict, context: list[dict],
               sample_input: str = "", sample_output: str = "", attachments: str = "") -> dict:
    out = await provider.complete(
        system=_PLAN_SYS,
        user=json.dumps({"task": "plan",
                         "description": _augment(description, sample_input, sample_output, attachments),
                         "classification": classification,
                         "context": [{"doc_id": c["doc_id"], "title": c["title"]} for c in context]}),
        json_mode=True,
    )
    brief = parse_json(out)
    brief.setdefault("summary", classification.get("pattern", "integration"))
    brief.setdefault("steps", [])
    brief.setdefault("error_handling", "")
    brief.setdefault("security", "")
    brief["citations"] = [{"doc_id": c["doc_id"], "title": c["title"]} for c in context]
    return brief


def generate_iflow(iflow_id: str, iflow_name: str, classification: dict, brief: dict) -> str:
    """Produce a full, editor-openable CPI iFlow model from the approved brief."""
    from ..iflow.serializer import build_iflow_xml
    return build_iflow_xml(iflow_id, iflow_name, classification or {}, brief or {})
