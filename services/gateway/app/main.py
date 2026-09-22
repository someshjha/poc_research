import asyncio
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .adapters import ADAPTERS, OllamaAdapter, ProviderError
from .schemas import CompareRequest, CompareResponse, GenerateRequest, GenerateResponse, ProviderStatus

app = FastAPI(title="Research Assistant — Model Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Suggested models shown in the UI when a hosted provider is configured.
# These are illustrative defaults; any model name the provider accepts can be
# passed to /v1/generate directly.
SUGGESTED_MODELS = {
    "openai": ["gpt-5.1"],
    "anthropic": ["claude-opus-5"],
    "google": ["gemini-3-pro"],
    "xai": ["grok-4"],
}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/v1/providers", response_model=list[ProviderStatus])
async def list_providers():
    statuses = []
    for name, adapter in ADAPTERS.items():
        if isinstance(adapter, OllamaAdapter):
            models = await adapter.list_models()
        else:
            models = SUGGESTED_MODELS.get(name, [])
        statuses.append(ProviderStatus(provider=name, configured=adapter.is_configured(), models=models))
    return statuses


async def _run_one(provider: str, model: str, prompt: str, system: str | None) -> GenerateResponse:
    adapter = ADAPTERS.get(provider)
    started = time.monotonic()
    if adapter is None:
        return GenerateResponse(
            provider=provider, model=model, text="", latency_ms=0, error=f"unknown provider '{provider}'"
        )
    try:
        result = await adapter.generate(model=model, prompt=prompt, system=system)
        latency_ms = int((time.monotonic() - started) * 1000)
        return GenerateResponse(provider=provider, model=model, text=result.text, latency_ms=latency_ms)
    except ProviderError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return GenerateResponse(provider=provider, model=model, text="", latency_ms=latency_ms, error=str(exc))


@app.post("/v1/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    return await _run_one(request.provider, request.model, request.prompt, request.system)


@app.post("/v1/compare", response_model=CompareResponse)
async def compare(request: CompareRequest):
    tasks = [
        _run_one(spec.provider, spec.model, request.prompt, request.system) for spec in request.models
    ]
    results = await asyncio.gather(*tasks)
    return CompareResponse(results=list(results))
