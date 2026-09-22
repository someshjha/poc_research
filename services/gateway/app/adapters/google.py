import os

import httpx

from .base import Adapter, GenerateResult, ProviderError


class GoogleAdapter(Adapter):
    name = "google"

    def __init__(self) -> None:
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.base_url = os.environ.get(
            "GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        )

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, model: str, prompt: str, system: str | None = None) -> GenerateResult:
        if not self.is_configured():
            raise ProviderError("GOOGLE_API_KEY is not set")

        payload: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/models/{model}:generateContent",
                params={"key": self.api_key},
                json=payload,
            )
        if response.status_code >= 400:
            raise ProviderError(f"Google error {response.status_code}: {response.text[:300]}")

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderError("Google returned no candidates (likely blocked by safety filters)")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        return GenerateResult(text=text, raw_model=model)
