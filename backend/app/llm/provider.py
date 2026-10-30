"""LLM provider abstraction (BYOK-ready).

The orchestrator depends only on :class:`LLMProvider`. A deterministic
:class:`StubProvider` lets the whole pipeline run and be tested without any API
key. Real providers (Azure OpenAI / OpenAI / Anthropic / Gemini / DeepSeek)
implement the same interface and are selected from the AI-engine settings —
prompts never leave the configured provider.
"""
from __future__ import annotations

import json
from typing import Protocol


class LLMProvider(Protocol):
    name: str

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        ...


class StubProvider:
    """Deterministic, offline provider. Returns structured, plausible output so
    the orchestrator, validators and quality gate exercise real logic."""

    name = "stub"

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        # The agents pass a compact JSON instruction in `user`; echo a shaped
        # response keyed on the requested "task".
        try:
            req = json.loads(user)
        except json.JSONDecodeError:
            return "OK"
        task = req.get("task")
        if task == "classify":
            return json.dumps(self._classify(req))
        if task == "plan":
            return json.dumps(self._plan(req))
        if task == "groovy":
            return self._groovy(req)
        return "OK"

    @staticmethod
    def _groovy(req: dict) -> str:
        text = (req.get("description") or "").lower()
        wants_json = any(k in text for k in ("json", "parse", "slurper"))
        wants_prop = "property" in text or "propert" in text
        wants_header = "header" in text
        wants_log = "log" in text
        wants_count = any(k in text for k in ("count", "size", "number of", "length"))

        lines = [
            "import com.sap.gateway.ip.core.customdev.util.Message",
            "import groovy.json.JsonSlurper" if wants_json else None,
            "import groovy.json.JsonOutput" if wants_json else None,
            "",
            "Message processData(Message message) {",
            "    def body = message.getBody(java.lang.String) as String",
        ]
        if wants_json:
            lines += [
                "    def parsed = new JsonSlurper().parseText(body ?: '{}')",
            ]
        if wants_count and wants_json:
            lines += [
                "    def count = (parsed instanceof List) ? parsed.size() "
                ": (parsed?.keySet()?.size() ?: 0)",
            ]
        if wants_prop:
            val = "count" if (wants_count and wants_json) else "'processed'"
            lines += [f"    message.setProperty('RCA_Status', {val})"]
        if wants_header:
            lines += ["    message.setHeader('X-RCA-Processed', 'true')"]
        if wants_log:
            lines += [
                "    def messageLog = messageLogFactory.getMessageLog(message)",
                "    messageLog?.addAttachmentAsString('RCA-Debug', body ?: '', 'text/plain')",
            ]
        if wants_json:
            lines += ["    message.setBody(JsonOutput.toJson(parsed))"]
        lines += [
            "    return message",
            "}",
        ]
        return "\n".join(l for l in lines if l is not None)

    @staticmethod
    def _classify(req: dict) -> dict:
        text = (req.get("description") or "").lower()
        adapters = []
        if any(k in text for k in ("http", "rest", "api")):
            adapters.append("HTTPS")
        if "soap" in text:
            adapters.append("SOAP")
        if any(k in text for k in ("odata", "s/4", "s4", "s/4hana")):
            adapters.append("OData")
        if any(k in text for k in ("jms", "queue")):
            adapters.append("JMS")
        if any(k in text for k in ("sftp", "file")):
            adapters.append("SFTP")
        if not adapters:
            adapters = ["HTTPS"]
        has_json = "{" in text or "json" in text
        has_xml = ("<" in text and ">" in text) or "xml" in text
        both_samples = "sample input" in text and "sample output" in text
        needs_mapping = (
            any(k in text for k in ("map", "json to xml", "transform", "convert", "structure",
                                    "xslt", "xsd", ".xsl", ".csv", "csv payload"))  # mapping/transform artifacts
            or (has_json and has_xml)     # format mismatch → transformation
            or both_samples               # providing I/O samples implies a mapping
        )
        return {
            "pattern": "point-to-point" if len(adapters) <= 2 else "content-based-routing",
            "sender": adapters[0],
            "receiver": adapters[-1] if len(adapters) > 1 else "OData",
            "needs_mapping": needs_mapping,
            "needs_groovy": "groovy" in text or "script" in text,
        }

    @staticmethod
    def _plan(req: dict) -> dict:
        c = req.get("classification", {})
        steps = [f"Receive via {c.get('sender', 'HTTPS')} sender adapter"]
        if c.get("needs_mapping"):
            steps.append("Message Mapping: source → target structure")
        if c.get("needs_groovy"):
            steps.append("Groovy script: custom transformation / enrichment")
        steps.append(f"Send to {c.get('receiver', 'OData')} receiver")
        return {
            "summary": f"{c.get('pattern', 'point-to-point')} integration "
                       f"{c.get('sender', 'HTTPS')} → {c.get('receiver', 'OData')}",
            "steps": steps,
            "error_handling": "Exception subprocess with retry (3x, exponential backoff) and MPL logging",
            "security": "OAuth2 client credentials; secrets from secure parameters, never inline",
        }


async def get_provider(settings, tenant_id: str) -> LLMProvider:  # noqa: ANN001
    """Factory. Returns the tenant's configured BYOK provider if set up,
    otherwise the deterministic stub."""
    from ..db import repos  # local import to avoid cycles

    row = await repos.get_ai(tenant_id)
    provider = row.provider if row else "stub"
    if provider == "stub" or not (row and row.key_enc):
        return StubProvider()

    key = await repos.get_ai_key(settings, tenant_id) or ""
    model = row.model or ""
    endpoint = row.endpoint or ""
    from .real_providers import AnthropicProvider, GeminiProvider, OpenAICompatProvider

    if provider in ("openai", "azure", "deepseek", "perplexity"):
        return OpenAICompatProvider(key, model, endpoint, flavor=provider)
    if provider == "anthropic":
        return AnthropicProvider(key, model, endpoint)
    if provider == "gemini":
        return GeminiProvider(key, model, endpoint)
    return StubProvider()


def parse_json(text: str) -> dict:
    """Parse a JSON object from an LLM response, tolerating code fences/prose."""
    import json
    import re

    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        # Non-JSON / empty response (e.g. a model that returned prose or only a
        # thinking block): degrade to an empty object so callers apply defaults
        # instead of raising a 500. The caller's setdefault() keeps output valid.
        return {}
