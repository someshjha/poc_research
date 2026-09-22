import os

import httpx

from .base import Adapter, GenerateResult, ProviderError


class OllamaAdapter(Adapter):
    """Always considered 'configured' — it's local, no API key needed."""

    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")

    def is_configured(self) -> bool:
        return True

    async def list_models(self) -> list[str]:
        """Chat/generation models only — embedding-only models (e.g. nomic-embed-text)
        can't answer /api/generate and are used internally by the retrieval service."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
            except httpx.HTTPError:
                return []
        names = [m["name"] for m in response.json().get("models", [])]
        return [name for name in names if "embed" not in name.lower()]

    async def generate(self, model: str, prompt: str, system: str | None = None) -> GenerateResult:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "system": system or "",
                    "stream": False,
                },
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"Ollama error {response.status_code}: {response.text[:300]} "
                f"(is '{model}' pulled? try `ollama pull {model}`)"
            )

        data = response.json()
        return GenerateResult(text=data.get("response", ""), raw_model=model)

    async def embed(self, model: str, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
        if response.status_code >= 400:
            raise ProviderError(f"Ollama embeddings error {response.status_code}: {response.text[:300]}")
        return response.json()["embedding"]
