"""Tests for Settings startup validation."""
import pytest


def test_missing_checkpoint_db_url_raises_in_production(monkeypatch):
    monkeypatch.delenv("CHECKPOINT_DB_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RAG_RELEVANCE_THRESHOLD", "0.7")
    monkeypatch.setenv("BUSINESS_HOURS_TIMEZONE", "Europe/London")
    from backend.config import Settings

    with pytest.raises(ValueError, match="CHECKPOINT_DB_URL"):
        Settings(_env_file=None)


def test_checkpoint_db_url_is_not_required_in_development(monkeypatch):
    monkeypatch.delenv("CHECKPOINT_DB_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    from backend.config import Settings

    s = Settings(_env_file=None)
    assert s.checkpoint_db_url == ""
