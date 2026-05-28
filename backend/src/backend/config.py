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

    model_config = {"env_file": str(_env_file), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
