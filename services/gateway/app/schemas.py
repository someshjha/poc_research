from pydantic import BaseModel


class ModelSpec(BaseModel):
    provider: str
    model: str


class GenerateRequest(BaseModel):
    provider: str
    model: str
    prompt: str
    system: str | None = None


class GenerateResponse(BaseModel):
    provider: str
    model: str
    text: str
    latency_ms: int
    error: str | None = None


class CompareRequest(BaseModel):
    prompt: str
    system: str | None = None
    models: list[ModelSpec]


class CompareResponse(BaseModel):
    results: list[GenerateResponse]


class ProviderStatus(BaseModel):
    provider: str
    configured: bool
    models: list[str] = []
