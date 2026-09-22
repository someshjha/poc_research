import os

import httpx

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8000")
RETRIEVAL_URL = os.environ.get("RETRIEVAL_URL", "http://retrieval:8000")
SIMULATION_URL = os.environ.get("SIMULATION_URL", "http://simulation:8000")


async def gateway_generate(provider: str, model: str, prompt: str, system: str | None = None) -> dict:
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{GATEWAY_URL}/v1/generate",
            json={"provider": provider, "model": model, "prompt": prompt, "system": system},
        )
    response.raise_for_status()
    return response.json()


async def gateway_compare(prompt: str, models: list[dict], system: str | None = None) -> dict:
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{GATEWAY_URL}/v1/compare",
            json={"prompt": prompt, "system": system, "models": models},
        )
    response.raise_for_status()
    return response.json()


async def retrieval_ingest(query: str, max_results: int = 5) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{RETRIEVAL_URL}/v1/ingest",
            json={"query": query, "max_results": max_results},
        )
    response.raise_for_status()
    return response.json()


async def simulation_run(lam: float, basis_size: int) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{SIMULATION_URL}/v1/simulate",
            json={"lambda": lam, "basis_size": basis_size},
        )
    response.raise_for_status()
    return response.json()
