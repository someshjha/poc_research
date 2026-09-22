from .anthropic import AnthropicAdapter
from .base import Adapter, GenerateResult, ProviderError
from .google import GoogleAdapter
from .ollama import OllamaAdapter
from .openai import OpenAIAdapter
from .xai import XAIAdapter

ADAPTERS: dict[str, Adapter] = {
    "openai": OpenAIAdapter(),
    "anthropic": AnthropicAdapter(),
    "google": GoogleAdapter(),
    "xai": XAIAdapter(),
    "ollama": OllamaAdapter(),
}

__all__ = [
    "Adapter",
    "GenerateResult",
    "ProviderError",
    "ADAPTERS",
]
