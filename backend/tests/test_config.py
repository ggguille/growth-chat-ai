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


def test_rag_proactive_threshold_defaults_to_relevance_plus_010(monkeypatch):
    monkeypatch.delenv("RAG_PROACTIVE_THRESHOLD", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RAG_RELEVANCE_THRESHOLD", "0.6")
    from backend.config import Settings

    s = Settings(_env_file=None)
    assert s.rag_proactive_threshold == pytest.approx(0.70)


def test_rag_proactive_threshold_explicit_value_is_preserved(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RAG_RELEVANCE_THRESHOLD", "0.6")
    monkeypatch.setenv("RAG_PROACTIVE_THRESHOLD", "0.85")
    from backend.config import Settings

    s = Settings(_env_file=None)
    assert s.rag_proactive_threshold == pytest.approx(0.85)
