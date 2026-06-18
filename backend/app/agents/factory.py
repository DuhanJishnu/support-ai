"""LLM Factory: provides a unified interface for instantiating LLM providers."""

from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from app.config import settings

T = TypeVar("T", bound=BaseChatModel)


def get_llm(
    temperature: float = 0,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Return a configured LLM instance (Gemini or Ollama).

    Uses Ollama if settings.USE_OLLAMA is True or if Gemini API key is missing/default.
    """
    if settings.USE_OLLAMA or not settings.is_gemini_available:
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
            **kwargs,
        )

    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
        **kwargs,
    )
