import os

import httpx

from .base import Adapter, GenerateResult, ProviderError


class XAIAdapter(Adapter):
    """xAI (Grok) exposes an OpenAI-compatible chat completions endpoint."""

    name = "xai"

    def __init__(self) -> None:
        self.api_key = os.environ.get("XAI_API_KEY")
        self.base_url = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, model: str, prompt: str, system: str | None = None) -> GenerateResult:
        if not self.is_configured():
            raise ProviderError("XAI_API_KEY is not set")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages},
            )
        if response.status_code >= 400:
            raise ProviderError(f"xAI error {response.status_code}: {response.text[:300]}")

        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return GenerateResult(text=text, raw_model=data.get("model", model))
