from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
