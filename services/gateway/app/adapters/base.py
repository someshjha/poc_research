from dataclasses import dataclass


class ProviderError(Exception):
    """Raised when a provider call fails or is not configured."""


@dataclass
class GenerateResult:
    text: str
    raw_model: str


class Adapter:
    """Common interface every provider adapter implements."""

    name: str

    def is_configured(self) -> bool:
        raise NotImplementedError

    async def generate(self, model: str, prompt: str, system: str | None = None) -> GenerateResult:
        raise NotImplementedError
