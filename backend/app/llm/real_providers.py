"""Real BYOK LLM providers, all implementing LLMProvider.complete().

Prompts never leave the configured provider. Networking uses httpx; the request
shapes follow each vendor's chat API. JSON-mode is requested where supported.
"""
from __future__ import annotations

import httpx

_TIMEOUT = 60.0


def _raise_for_status(r: httpx.Response, provider: str) -> None:
    """Raise with the provider's actual error body so the reason is visible."""
    if r.status_code >= 400:
        detail = r.text[:400].replace("\n", " ").strip()
        raise RuntimeError(f"{provider} HTTP {r.status_code}: {detail}")


def _require_model(model: str, provider: str) -> None:
    if not model or not model.strip():
        raise ValueError(
            f"Model is required for {provider}. Enter the exact model string "
            "(e.g. claude-sonnet-4-20250514, gpt-4o, gemini-1.5-pro)."
        )


class OpenAICompatProvider:
    """OpenAI, Azure OpenAI, DeepSeek and Perplexity share the OpenAI chat-completions shape."""

    def __init__(self, api_key: str, model: str, endpoint: str = "", flavor: str = "openai") -> None:
        self.api_key = api_key
        self.model = model
        self.flavor = flavor
        self.name = flavor
        if flavor == "azure":
            # endpoint = https://<res>.openai.azure.com ; OpenAI-compatible v1 path
            self.url = f"{endpoint.rstrip('/')}/openai/v1/chat/completions"
        elif flavor == "deepseek":
            self.url = (endpoint or "https://api.deepseek.com").rstrip("/") + "/chat/completions"
        elif flavor == "perplexity":
            self.url = (endpoint or "https://api.perplexity.ai").rstrip("/") + "/chat/completions"
        else:
            self.url = (endpoint or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        _require_model(self.model, self.flavor)
        # NOTE: `temperature` is intentionally omitted. Newer OpenAI models
        # (gpt-5 family) reject any non-default temperature with HTTP 400, so we
        # let each provider use its own default for maximum compatibility.
        sys = system
        body: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": sys}, {"role": "user", "content": user}],
        }
        if json_mode:
            if self.flavor == "perplexity":
                # Perplexity rejects response_format.type "json_object" (accepts
                # only "json_schema" or "text"). Instruct JSON via the prompt and
                # let the tolerant parser extract the object.
                sys = system + "\nRespond with a single valid JSON object and nothing else."
                body["messages"][0]["content"] = sys
            else:
                body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.flavor == "azure":
            headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(self.url, json=body, headers=headers)
            _raise_for_status(r, self.flavor)
            return r.json()["choices"][0]["message"]["content"]


class AnthropicProvider:
    def __init__(self, api_key: str, model: str, endpoint: str = "") -> None:
        self.api_key = api_key
        self.model = model
        self.name = "anthropic"
        self.url = (endpoint or "https://api.anthropic.com").rstrip("/") + "/v1/messages"

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        _require_model(self.model, "anthropic")
        sys = system + ("\nRespond with a single valid JSON object and nothing else." if json_mode else "")
        body = {
            "model": self.model,
            "max_tokens": 2048,
            "system": sys,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(self.url, json=body, headers=headers)
            _raise_for_status(r, "anthropic")
            blocks = r.json().get("content", [])
            # pick the first text block (newer models may emit thinking blocks first)
            return next((b.get("text", "") for b in blocks if b.get("type") == "text"), "")


class GeminiProvider:
    def __init__(self, api_key: str, model: str, endpoint: str = "") -> None:
        self.api_key = api_key
        self.model = model
        self.name = "gemini"
        base = (endpoint or "https://generativelanguage.googleapis.com").rstrip("/")
        self.url = f"{base}/v1beta/models/{model}:generateContent"

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        _require_model(self.model, "gemini")
        body: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.1},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(self.url, json=body, headers={"Content-Type": "application/json"},
                                  params={"key": self.api_key})
            _raise_for_status(r, "gemini")
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
