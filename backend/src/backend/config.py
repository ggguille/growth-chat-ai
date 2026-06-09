from pathlib import Path

from pydantic_settings import BaseSettings

_env_file = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    app_env: str = "development"
    zgc_api_key: str = ""
    llm_stream_timeout_ms: int = 10000
    slack_webhook_url: str = ""
    slack_bot_token: str = ""
    checkpoint_db_url: str = ""
    fallback_email_address: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    allowed_origin: str = "http://localhost:3000"

    # LLM — production (Anthropic)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # LLM — development (Ollama, ADR-001: Llama 3.1 8B)
    ollama_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://localhost:11434"

    # Analytics (Langfuse) — optional; NullProvider used when unset
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    # RAG — required in all environments, no default (service will not start if unset)
    rag_relevance_threshold: float = 0.0  # validated below
    rag_top_k: int = 5
    knowledge_table_name: str = "knowledge_chunks"
    openai_api_key: str = ""

    # Conversation orchestrator
    stall_turn_threshold: int = 6
    context_window_turns: int = 10

    # Business hours — required, no default (service will not start if unset)
    business_hours_timezone: str = ""  # validated below

    model_config = {"env_file": str(_env_file), "env_file_encoding": "utf-8", "extra": "ignore"}

    def model_post_init(self, __context) -> None:
        if self.app_env != "development":
            if not self.rag_relevance_threshold:
                raise ValueError("RAG_RELEVANCE_THRESHOLD must be set (non-zero) in non-development environments")
            if not self.business_hours_timezone:
                raise ValueError("BUSINESS_HOURS_TIMEZONE must be set in non-development environments")


settings = Settings()
