import os

import httpx

from .base import Adapter, GenerateResult, ProviderError


class AnthropicAdapter(Adapter):
    name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        self.api_version = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")

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

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.api_version,
                },
                json=payload,
            )
        if response.status_code >= 400:
            raise ProviderError(f"Anthropic error {response.status_code}: {response.text[:300]}")

        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return GenerateResult(text=text, raw_model=data.get("model", model))
