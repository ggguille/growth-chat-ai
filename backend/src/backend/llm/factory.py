from telemetry import get_logger

from backend.llm.anthropic_client import AnthropicLLMClient
from backend.llm.base import BaseLLMClient
from backend.llm.ollama_client import OllamaLLMClient

log = get_logger("orchestrator")


def create_llm_client(settings) -> BaseLLMClient:
    """Select LLM backend based on environment (ADR-001).

    Development / no API key → Ollama (Llama 4 8B, local, no cost).
    Production with ANTHROPIC_API_KEY → Anthropic Claude Haiku 4.5.
    """
    if settings.app_env == "development" or not settings.anthropic_api_key:
        log.info("llm_backend_selected", session_id=None, backend="ollama", model=settings.ollama_model, base_url=settings.ollama_base_url)
        return OllamaLLMClient(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )

    log.info("llm_backend_selected", session_id=None, backend="anthropic", model=settings.anthropic_model)
    return AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )
