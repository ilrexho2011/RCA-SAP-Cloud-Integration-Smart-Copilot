"""Groovy script generation for SAP CPI script steps."""
from __future__ import annotations

import json

from ..llm.provider import LLMProvider

_SYS = (
    "You write SAP Cloud Integration Groovy scripts. Output ONLY Groovy code, no "
    "markdown fences, no prose. The entry point must be "
    "'Message processData(Message message)', importing "
    "com.sap.gateway.ip.core.customdev.util.Message, and it must 'return message'. "
    "Never log secrets. Keep it idempotent."
)


async def generate(provider: LLMProvider, description: str) -> str:
    code = await provider.complete(
        system=_SYS,
        user=json.dumps({"task": "groovy", "description": description}),
        json_mode=False,
    )
    return _strip_fences(code).strip()


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        import re
        t = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", t).strip()
    return t
