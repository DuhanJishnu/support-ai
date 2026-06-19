"""Tests for Ollama fallback logic and LLM factory."""

from unittest.mock import patch

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from app.agents.factory import get_llm
from app.config import Settings


def test_get_llm_uses_ollama_when_gemini_missing():
    """Verify that Ollama is used when the Gemini API key is the default placeholder."""
    # Create settings with default key
    settings = Settings()
    # Ensure it's the default
    assert not settings.is_gemini_available

    with patch("app.agents.factory.settings", settings):
        llm = get_llm()
        assert isinstance(llm, ChatOllama)
        assert llm.model == settings.OLLAMA_MODEL


def test_get_llm_uses_gemini_when_key_provided_and_no_ollama():
    """Verify that Gemini is used when a real-ish API key is provided."""
    settings = Settings()
    settings.GOOGLE_API_KEY = "real_key_123"
    settings.USE_OLLAMA = False
    assert settings.is_gemini_available

    with patch("app.agents.factory.settings", settings):
        llm = get_llm()
        assert isinstance(llm, ChatGoogleGenerativeAI)
        assert llm.google_api_key.get_secret_value() == "real_key_123"


def test_get_llm_uses_ollama_when_forced():
    """Verify that Ollama is used when USE_OLLAMA is True, even if Gemini key exists."""
    settings = Settings()
    settings.GOOGLE_API_KEY = "real_key_123"
    settings.USE_OLLAMA = True

    with patch("app.agents.factory.settings", settings):
        llm = get_llm()
        assert isinstance(llm, ChatOllama)
