import logging

from backend.llm.anthropic_client import AnthropicLLMClient
from backend.llm.base import BaseLLMClient
from backend.llm.ollama_client import OllamaLLMClient

logger = logging.getLogger(__name__)


def create_llm_client(settings) -> BaseLLMClient:
    """Select LLM backend based on environment (ADR-001).

    Development / no API key → Ollama (Llama 4 8B, local, no cost).
    Production with ANTHROPIC_API_KEY → Anthropic Claude Haiku 4.5.
    """
    if settings.app_env == "development" or not settings.anthropic_api_key:
        logger.info("LLM backend: Ollama (%s @ %s)", settings.ollama_model, settings.ollama_base_url)
        return OllamaLLMClient(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )

    logger.info("LLM backend: Anthropic (%s)", settings.anthropic_model)
    return AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )
