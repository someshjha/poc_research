import asyncio
import os

import httpx

from .base import Adapter, GenerateResult, ProviderError


class AnthropicAdapter(Adapter):
    name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        self.api_version = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
        # Some Console API keys are scoped to an organization rather than a
        # single workspace; those require this header on every request.
        self.workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, model: str, prompt: str, system: str | None = None) -> GenerateResult:
        if not self.is_configured():
            raise ProviderError("ANTHROPIC_API_KEY is not set")

        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            # httpx sends no Accept header by default; Anthropic's edge
            # silently 404s requests that omit one instead of routing them
            # to the API, so this is required, not cosmetic.
            "accept": "application/json",
        }
        if self.workspace_id:
            headers["anthropic-workspace-id"] = self.workspace_id

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.base_url}/messages", headers=headers, json=payload)
            # Anthropic's edge occasionally returns an empty 404 for a valid
            # request (observed, intermittent — not a routing bug on our
            # side); one quick retry clears it almost every time.
            if response.status_code == 404 and not response.text:
                await asyncio.sleep(0.3)
                response = await client.post(f"{self.base_url}/messages", headers=headers, json=payload)
        if response.status_code >= 400:
            hint = ""
            if response.status_code == 400 and "workspace" in response.text.lower():
                hint = " (this key is org-scoped — set ANTHROPIC_WORKSPACE_ID, or use a workspace-scoped key instead)"
            raise ProviderError(f"Anthropic error {response.status_code}: {response.text[:300]}{hint}")

        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return GenerateResult(text=text, raw_model=data.get("model", model))
